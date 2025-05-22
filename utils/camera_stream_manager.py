# utils/camera_stream_manager.py

import os
import cv2
import json
import redis
import asyncio
import threading
import time
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Any, List
from dataclasses import dataclass, asdict
from django.conf import settings
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import gi

# GStreamer initialization
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GstApp, GLib

# Initialize GStreamer
Gst.init(None)

logger = logging.getLogger('security_ai')

@dataclass
class StreamSession:
    """Stream session data structure"""
    camera_id: str
    user_id: str
    session_id: str
    created_at: datetime
    last_activity: datetime
    client_count: int = 0
    is_active: bool = True
    quality: str = 'medium'  # low, medium, high
    fps: int = 15

@dataclass
class StreamMetadata:
    """Stream metadata structure"""
    camera_id: str
    width: int
    height: int
    fps: int
    codec: str
    bitrate: int
    last_frame_time: datetime
    total_frames: int = 0
    dropped_frames: int = 0

class RedisStreamManager:
    """Redis-based stream management with advanced features"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 0),
            decode_responses=True
        )
        self.redis_binary = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 1),  # Different DB for binary data
            decode_responses=False
        )
        
        # Cache configuration
        self.frame_cache_ttl = 5  # seconds
        self.session_ttl = 3600   # 1 hour
        self.metadata_ttl = 86400 # 24 hours
        
    def create_session(self, camera_id: str, user_id: str, session_id: str, quality: str = 'medium') -> StreamSession:
        """Create a new streaming session"""
        session = StreamSession(
            camera_id=camera_id,
            user_id=user_id,
            session_id=session_id,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            quality=quality,
            fps=self._get_fps_for_quality(quality)
        )
        
        # Store session in Redis
        session_key = f"stream:session:{session_id}"
        self.redis_client.hset(session_key, mapping=asdict(session))
        self.redis_client.expire(session_key, self.session_ttl)
        
        # Add to camera sessions set
        camera_sessions_key = f"stream:camera:{camera_id}:sessions"
        self.redis_client.sadd(camera_sessions_key, session_id)
        self.redis_client.expire(camera_sessions_key, self.session_ttl)
        
        # Add to user sessions set
        user_sessions_key = f"stream:user:{user_id}:sessions"
        self.redis_client.sadd(user_sessions_key, session_id)
        self.redis_client.expire(user_sessions_key, self.session_ttl)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[StreamSession]:
        """Get streaming session by ID"""
        session_key = f"stream:session:{session_id}"
        data = self.redis_client.hgetall(session_key)
        
        if not data:
            return None
            
        # Convert string timestamps back to datetime
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        data['client_count'] = int(data['client_count'])
        data['is_active'] = data['is_active'] == 'True'
        data['fps'] = int(data['fps'])
        
        return StreamSession(**data)
    
    def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity timestamp"""
        session_key = f"stream:session:{session_id}"
        if self.redis_client.exists(session_key):
            self.redis_client.hset(session_key, 'last_activity', datetime.now().isoformat())
            self.redis_client.expire(session_key, self.session_ttl)
            return True
        return False
    
    def increment_client_count(self, session_id: str) -> int:
        """Increment client count for session"""
        session_key = f"stream:session:{session_id}"
        return self.redis_client.hincrby(session_key, 'client_count', 1)
    
    def decrement_client_count(self, session_id: str) -> int:
        """Decrement client count for session"""
        session_key = f"stream:session:{session_id}"
        count = self.redis_client.hincrby(session_key, 'client_count', -1)
        return max(0, count)
    
    def end_session(self, session_id: str) -> bool:
        """End a streaming session"""
        session = self.get_session(session_id)
        if not session:
            return False
            
        # Remove from camera sessions
        camera_sessions_key = f"stream:camera:{session.camera_id}:sessions"
        self.redis_client.srem(camera_sessions_key, session_id)
        
        # Remove from user sessions
        user_sessions_key = f"stream:user:{session.user_id}:sessions"
        self.redis_client.srem(user_sessions_key, session_id)
        
        # Delete session
        session_key = f"stream:session:{session_id}"
        self.redis_client.delete(session_key)
        
        # Clean up frame cache
        self.cleanup_frame_cache(session.camera_id, session_id)
        
        return True
    
    def cache_frame(self, camera_id: str, session_id: str, frame: np.ndarray, frame_number: int):
        """Cache frame in Redis with compression"""
        try:
            # Encode frame as JPEG for compression
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            
            # Store in Redis
            frame_key = f"stream:frame:{camera_id}:{session_id}:{frame_number}"
            self.redis_binary.setex(frame_key, self.frame_cache_ttl, buffer.tobytes())
            
            # Update latest frame pointer
            latest_key = f"stream:latest:{camera_id}:{session_id}"
            self.redis_client.setex(latest_key, self.frame_cache_ttl, frame_number)
            
        except Exception as e:
            logger.error(f"Error caching frame: {str(e)}")
    
    def get_cached_frame(self, camera_id: str, session_id: str, frame_number: int = None) -> Optional[np.ndarray]:
        """Get cached frame from Redis"""
        try:
            if frame_number is None:
                # Get latest frame
                latest_key = f"stream:latest:{camera_id}:{session_id}"
                frame_number = self.redis_client.get(latest_key)
                if not frame_number:
                    return None
                frame_number = int(frame_number)
            
            frame_key = f"stream:frame:{camera_id}:{session_id}:{frame_number}"
            buffer = self.redis_binary.get(frame_key)
            
            if not buffer:
                return None
                
            # Decode frame
            nparr = np.frombuffer(buffer, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            return frame
            
        except Exception as e:
            logger.error(f"Error getting cached frame: {str(e)}")
            return None
    
    def cleanup_frame_cache(self, camera_id: str, session_id: str):
        """Clean up frame cache for a session"""
        pattern = f"stream:frame:{camera_id}:{session_id}:*"
        keys = self.redis_binary.keys(pattern)
        if keys:
            self.redis_binary.delete(*keys)
        
        # Clean up latest frame pointer
        latest_key = f"stream:latest:{camera_id}:{session_id}"
        self.redis_client.delete(latest_key)
    
    def store_metadata(self, camera_id: str, metadata: StreamMetadata):
        """Store stream metadata"""
        metadata_key = f"stream:metadata:{camera_id}"
        data = asdict(metadata)
        data['last_frame_time'] = data['last_frame_time'].isoformat()
        
        self.redis_client.hset(metadata_key, mapping=data)
        self.redis_client.expire(metadata_key, self.metadata_ttl)
    
    def get_metadata(self, camera_id: str) -> Optional[StreamMetadata]:
        """Get stream metadata"""
        metadata_key = f"stream:metadata:{camera_id}"
        data = self.redis_client.hgetall(metadata_key)
        
        if not data:
            return None
        
        # Convert data types
        data['width'] = int(data['width'])
        data['height'] = int(data['height'])
        data['fps'] = int(data['fps'])
        data['bitrate'] = int(data['bitrate'])
        data['total_frames'] = int(data['total_frames'])
        data['dropped_frames'] = int(data['dropped_frames'])
        data['last_frame_time'] = datetime.fromisoformat(data['last_frame_time'])
        
        return StreamMetadata(**data)
    
    def get_camera_sessions(self, camera_id: str) -> List[str]:
        """Get all active sessions for a camera"""
        camera_sessions_key = f"stream:camera:{camera_id}:sessions"
        return list(self.redis_client.smembers(camera_sessions_key))
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        pattern = "stream:session:*"
        keys = self.redis_client.keys(pattern)
        
        for key in keys:
            session_data = self.redis_client.hgetall(key)
            if session_data:
                last_activity = datetime.fromisoformat(session_data.get('last_activity', ''))
                if datetime.now() - last_activity > timedelta(minutes=30):  # 30 minutes timeout
                    session_id = key.split(':')[-1]
                    self.end_session(session_id)
    
    def _get_fps_for_quality(self, quality: str) -> int:
        """Get FPS based on quality setting"""
        fps_map = {
            'low': 10,
            'medium': 15,
            'high': 30
        }
        return fps_map.get(quality, 15)

class GStreamerPipeline:
    """GStreamer pipeline for hardware-accelerated video processing"""
    
    def __init__(self, camera_url: str, session: StreamSession):
        self.camera_url = camera_url
        self.session = session
        self.pipeline = None
        self.appsink = None
        self.is_running = False
        self.frame_callback = None
        self.use_gpu = self._detect_gpu_support()
        
    def _detect_gpu_support(self) -> bool:
        """Detect available GPU acceleration"""
        try:
            # Check for NVIDIA GPU support
            pipeline_str = "nvdec ! nvvidconv ! video/x-raw,format=BGRx ! appsink"
            test_pipeline = Gst.parse_launch(f"videotestsrc num-buffers=1 ! {pipeline_str}")
            if test_pipeline:
                return True
        except:
            pass
            
        try:
            # Check for Intel GPU support
            pipeline_str = "vaapidecodebin ! vaapipostproc ! video/x-raw,format=BGRx ! appsink"
            test_pipeline = Gst.parse_launch(f"videotestsrc num-buffers=1 ! {pipeline_str}")
            if test_pipeline:
                return True
        except:
            pass
            
        return False
    
    def create_pipeline(self) -> bool:
        """Create GStreamer pipeline with GPU acceleration if available"""
        try:
            # Determine source element based on URL
            if self.camera_url.startswith('rtsp://'):
                source = f"rtspsrc location={self.camera_url} latency=0 drop-on-latency=true"
            elif self.camera_url.startswith('http://') or self.camera_url.startswith('https://'):
                source = f"souphttpsrc location={self.camera_url}"
            elif self.camera_url.startswith('/dev/video'):
                source = f"v4l2src device={self.camera_url}"
            else:
                source = f"filesrc location={self.camera_url}"
            
            # Build pipeline based on GPU support
            if self.use_gpu:
                # GPU-accelerated pipeline
                pipeline_str = (
                    f"{source} ! "
                    "rtph264depay ! h264parse ! "
                    "nvdec ! nvvidconv ! "
                    "video/x-raw,format=BGRx ! "
                    "videorate ! videoconvert ! "
                    f"video/x-raw,framerate={self.session.fps}/1 ! "
                    "appsink name=sink emit-signals=true sync=false max-buffers=2 drop=true"
                )
            else:
                # CPU pipeline
                pipeline_str = (
                    f"{source} ! "
                    "decodebin ! videoconvert ! "
                    "videorate ! "
                    f"video/x-raw,framerate={self.session.fps}/1 ! "
                    "appsink name=sink emit-signals=true sync=false max-buffers=2 drop=true"
                )
            
            # Create pipeline
            self.pipeline = Gst.parse_launch(pipeline_str)
            if not self.pipeline:
                return False
            
            # Get appsink element
            self.appsink = self.pipeline.get_by_name('sink')
            if not self.appsink:
                return False
            
            # Connect to new-sample signal
            self.appsink.connect('new-sample', self._on_new_sample)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating GStreamer pipeline: {str(e)}")
            return False
    
    def start(self) -> bool:
        """Start the pipeline"""
        if not self.pipeline:
            if not self.create_pipeline():
                return False
        
        # Start pipeline
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("Failed to start GStreamer pipeline")
            return False
        
        self.is_running = True
        return True
    
    def stop(self):
        """Stop the pipeline"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        self.is_running = False
    
    def set_frame_callback(self, callback):
        """Set callback function for new frames"""
        self.frame_callback = callback
    
    def _on_new_sample(self, appsink):
        """Handle new sample from appsink"""
        try:
            sample = appsink.emit('pull-sample')
            if not sample:
                return Gst.FlowReturn.ERROR
            
            # Get buffer
            buffer = sample.get_buffer()
            if not buffer:
                return Gst.FlowReturn.ERROR
                
            # Get caps
            caps = sample.get_caps()
            if not caps:
                return Gst.FlowReturn.ERROR
            
            # Extract frame info
            structure = caps.get_structure(0)
            width = structure.get_int('width')[1]
            height = structure.get_int('height')[1]
            
            # Map buffer
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.ERROR
            
            try:
                # Convert to numpy array
                frame_data = np.frombuffer(map_info.data, dtype=np.uint8)
                
                # Reshape based on format
                if structure.get_string('format') == 'BGRx':
                    frame = frame_data.reshape((height, width, 4))[:, :, :3]  # Remove alpha channel
                else:
                    frame = frame_data.reshape((height, width, 3))
                
                # Call frame callback
                if self.frame_callback:
                    self.frame_callback(frame)
                    
            finally:
                buffer.unmap(map_info)
            
            return Gst.FlowReturn.OK
            
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
            return Gst.FlowReturn.ERROR

class CameraStreamManager:
    """Main camera streaming manager with Redis and GStreamer"""
    
    def __init__(self):
        self.redis_manager = RedisStreamManager()
        self.active_pipelines: Dict[str, GStreamerPipeline] = {}
        self.frame_counters: Dict[str, int] = {}
        self.channel_layer = get_channel_layer()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        
    def start_stream(self, camera_id: str, user_id: str, session_id: str, 
                    camera_url: str, quality: str = 'medium') -> bool:
        """Start streaming for a camera"""
        try:
            # Create session
            session = self.redis_manager.create_session(camera_id, user_id, session_id, quality)
            
            # Check if pipeline already exists for this camera
            pipeline_key = f"{camera_id}_{session_id}"
            
            if pipeline_key not in self.active_pipelines:
                # Create new pipeline
                pipeline = GStreamerPipeline(camera_url, session)
                
                # Set frame callback
                pipeline.set_frame_callback(
                    lambda frame: self._handle_new_frame(camera_id, session_id, frame)
                )
                
                # Start pipeline
                if not pipeline.start():
                    return False
                
                self.active_pipelines[pipeline_key] = pipeline
                self.frame_counters[pipeline_key] = 0
                
                logger.info(f"Started stream for camera {camera_id}, session {session_id}")
            
            # Increment client count
            self.redis_manager.increment_client_count(session_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting stream: {str(e)}")
            return False
    
    def stop_stream(self, camera_id: str, session_id: str) -> bool:
        """Stop streaming for a camera session"""
        try:
            pipeline_key = f"{camera_id}_{session_id}"
            
            # Decrement client count
            client_count = self.redis_manager.decrement_client_count(session_id)
            
            # If no more clients, stop pipeline
            if client_count <= 0:
                if pipeline_key in self.active_pipelines:
                    self.active_pipelines[pipeline_key].stop()
                    del self.active_pipelines[pipeline_key]
                    
                if pipeline_key in self.frame_counters:
                    del self.frame_counters[pipeline_key]
                
                # End session
                self.redis_manager.end_session(session_id)
                
                logger.info(f"Stopped stream for camera {camera_id}, session {session_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping stream: {str(e)}")
            return False
    
    def get_stream_frame(self, camera_id: str, session_id: str) -> Optional[bytes]:
        """Get latest frame as JPEG bytes"""
        try:
            frame = self.redis_manager.get_cached_frame(camera_id, session_id)
            if frame is None:
                return None
            
            # Encode as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            
            return buffer.tobytes()
            
        except Exception as e:
            logger.error(f"Error getting stream frame: {str(e)}")
            return None
    
    def _handle_new_frame(self, camera_id: str, session_id: str, frame: np.ndarray):
        """Handle new frame from pipeline"""
        try:
            pipeline_key = f"{camera_id}_{session_id}"
            
            # Increment frame counter
            self.frame_counters[pipeline_key] = self.frame_counters.get(pipeline_key, 0) + 1
            frame_number = self.frame_counters[pipeline_key]
            
            # Cache frame
            self.redis_manager.cache_frame(camera_id, session_id, frame, frame_number)
            
            # Update session activity
            self.redis_manager.update_session_activity(session_id)
            
            # Send frame via WebSocket
            if self.channel_layer:
                group_name = f"camera_{camera_id}"
                
                # Encode frame as base64 for WebSocket transmission
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                _, buffer = cv2.imencode('.jpg', frame, encode_param)
                frame_b64 = buffer.tobytes()
                
                async_to_sync(self.channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'stream_frame',
                        'camera_id': camera_id,
                        'session_id': session_id,
                        'frame': frame_b64,
                        'frame_number': frame_number,
                        'timestamp': time.time()
                    }
                )
            
            # Update metadata
            metadata = StreamMetadata(
                camera_id=camera_id,
                width=frame.shape[1],
                height=frame.shape[0],
                fps=15,  # This should be calculated
                codec='h264',
                bitrate=0,  # This should be calculated
                last_frame_time=datetime.now(),
                total_frames=frame_number
            )
            self.redis_manager.store_metadata(camera_id, metadata)
            
        except Exception as e:
            logger.error(f"Error handling new frame: {str(e)}")
    
    def _cleanup_worker(self):
        """Background worker for cleanup tasks"""
        while True:
            try:
                # Clean up expired sessions
                self.redis_manager.cleanup_expired_sessions()
                
                # Sleep for 60 seconds
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in cleanup worker: {str(e)}")
                time.sleep(60)
    
    def get_stream_stats(self, camera_id: str) -> Dict[str, Any]:
        """Get streaming statistics for a camera"""
        try:
            sessions = self.redis_manager.get_camera_sessions(camera_id)
            metadata = self.redis_manager.get_metadata(camera_id)
            
            stats = {
                'camera_id': camera_id,
                'active_sessions': len(sessions),
                'sessions': sessions,
                'metadata': asdict(metadata) if metadata else None
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stream stats: {str(e)}")
            return {}

# Global instance
stream_manager = CameraStreamManager()