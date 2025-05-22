# streaming/stream_manager.py
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GstApp, GLib

import cv2
import redis
import json
import time
import base64
import threading
import logging
from typing import Dict, Optional
from django.conf import settings
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from cameras.models import Camera
from detectors import FireSmokeDetector, FallDetector, ViolenceDetector, ChokingDetector
Gst.init(None)

logger = logging.getLogger('security_ai')

class IntegratedStreamManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.channel_layer = get_channel_layer()
        self.active_streams = {}
        self.stream_locks = {}
        self.background_tasks_running = False
        self.detectors = {
            'fire_smoke': FireSmokeDetector(),
            'fall': FallDetector(),
            'violence': ViolenceDetector(),
            'choking': ChokingDetector()
        }
    
    def start_camera_stream(self, camera_id: int, use_gstreamer: bool = True) -> Dict:
        try:
            camera = Camera.objects.get(id=camera_id)
            if camera_id in self.active_streams:
                self.stop_camera_stream(camera_id)
            session_id = f"camera_{camera_id}_{int(time.time())}"
            group_name = f"stream_{session_id}"
            if use_gstreamer and self._can_use_gstreamer(camera):
                streamer = GStreamerAIStreamer(camera, session_id, group_name, self.detectors)
            else:
                streamer = OpenCVAIStreamer(camera, session_id, group_name, self.detectors)
            if streamer.start():
                self.active_streams[camera_id] = streamer
                self.stream_locks[camera_id] = threading.Lock()
                self._save_session_info(session_id, camera, group_name)
                camera.status = 'online'
                camera.last_online = timezone.now()
                camera.save(update_fields=['status', 'last_online'])
                
                return {
                    'success': True,
                    'session_id': session_id,
                    'group_name': group_name,
                    'stream_type': 'gstreamer' if use_gstreamer else 'opencv'
                }
            else:
                return {
                    'success': False,
                    'error': 'Stream failed'
                }
                
        except Camera.DoesNotExist:
            return {
                'success': False,
                'error': 'Not found camera'
            }
        except Exception as e:
            logger.error(f"Stream start error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def stop_camera_stream(self, camera_id: int) -> Dict:
        try:
            if camera_id in self.active_streams:
                with self.stream_locks.get(camera_id, threading.Lock()):
                    streamer = self.active_streams.pop(camera_id)
                    streamer.stop()
                    self._cleanup_session(streamer.session_id)
                    
                    if camera_id in self.stream_locks:
                        del self.stream_locks[camera_id]
                    
                    return {
                        'success': True,
                        'message': 'Stoped stream!'
                    }
            else:
                return {
                    'success': False,
                    'error': 'No active stream!'
                }
                
        except Exception as e:
            logger.error(f"Stream stop error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_stream_status(self, camera_id: int) -> Dict:
        try:
            if camera_id in self.active_streams:
                streamer = self.active_streams[camera_id]
                metrics = self._get_stream_metrics(streamer.session_id)
                
                return {
                    'success': True,
                    'is_active': True,
                    'session_id': streamer.session_id,
                    'group_name': streamer.group_name,
                    'metrics': metrics
                }
            else:
                return {
                    'success': True,
                    'is_active': False,
                    'session_id': None,
                    'group_name': None,
                    'metrics': None
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _can_use_gstreamer(self, camera) -> bool:
        return camera.stream_url.startswith(('rtsp://', 'http://', 'https://'))
    
    def _save_session_info(self, session_id: str, camera, group_name: str):
        session_data = {
            'session_id': session_id,
            'camera_id': camera.id,
            'camera_name': camera.name,
            'stream_url': camera.stream_url,
            'group_name': group_name,
            'created_at': time.time(),
            'status': 'active'
        }
        
        self.redis_client.setex(
            f"session:{session_id}",
            settings.STREAMING_SETTINGS['SESSION_TIMEOUT'],
            json.dumps(session_data)
        )
        
        self.redis_client.sadd("active_sessions", session_id)
    
    def _cleanup_session(self, session_id: str):
        keys_to_delete = [
            f"session:{session_id}",
            f"frame:{session_id}",
            f"frame_meta:{session_id}",
            f"metrics:{session_id}"
        ]
        
        for key in keys_to_delete:
            self.redis_client.delete(key)
        
        self.redis_client.srem("active_sessions", session_id)
    
    def _get_stream_metrics(self, session_id: str) -> Optional[Dict]:
        metrics_data = self.redis_client.get(f"metrics:{session_id}")
        return json.loads(metrics_data) if metrics_data else None
    
    def start_background_tasks(self):
        if not self.background_tasks_running:
            self.background_tasks_running = True
            cleanup_thread = threading.Thread(target=self._cleanup_expired_sessions)
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            metrics_thread = threading.Thread(target=self._collect_metrics)
            metrics_thread.daemon = True
            metrics_thread.start()
    
    def _cleanup_expired_sessions(self):
        while self.background_tasks_running:
            try:
                current_time = time.time()
                active_sessions = self.redis_client.smembers("active_sessions")
                
                for session_id in active_sessions:
                    session_data = self.redis_client.get(f"session:{session_id}")
                    if session_data:
                        session = json.loads(session_data)
                        created_at = session.get('created_at', 0)
                        
                        if current_time - created_at > settings.STREAMING_SETTINGS['SESSION_TIMEOUT']:
                            self._cleanup_session(session_id)
                            logger.info(f"Expeired session management: {session_id}")
                
                time.sleep(settings.STREAMING_SETTINGS['CLEANUP_INTERVAL'])
                
            except Exception as e:
                logger.error(f"Session error!: {e}")
                time.sleep(60)
    
    def _collect_metrics(self):
        while self.background_tasks_running:
            try:
                for camera_id, streamer in self.active_streams.items():
                    metrics = streamer.get_metrics()
                    if metrics:
                        self.redis_client.setex(
                            f"metrics:{streamer.session_id}",
                            300,  
                            json.dumps(metrics)
                        )
                
                time.sleep(settings.STREAMING_SETTINGS['MONITORING_INTERVAL'])
                
            except Exception as e:
                logger.error(f"Metric collection error: {e}")
                time.sleep(30)


class BaseAIStreamer:
    def __init__(self, camera, session_id: str, group_name: str, detectors: Dict):
        self.camera = camera
        self.session_id = session_id
        self.group_name = group_name
        self.detectors = detectors
        self.channel_layer = get_channel_layer()
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )
        
        self.is_streaming = False
        self.frame_count = 0
        self.detection_count = 0
        self.last_frame_time = 0
        self.metrics = {
            'fps': 0,
            'frame_count': 0,
            'detection_count': 0,
            'start_time': time.time()
        }
    
    def process_detection(self, frame):
        try:
            if not self.camera.detection_enabled:
                return frame, []
            
            detections = []
            annotated_frame = frame.copy()
            
            detection_types = []
            if self.camera.fire_smoke_detection:
                detection_types.append('fire_smoke')
            if self.camera.fall_detection:
                detection_types.append('fall')
            if self.camera.violence_detection:
                detection_types.append('violence')
            if self.camera.choking_detection:
                detection_types.append('choking')
            
            for detection_type in detection_types:
                if detection_type in self.detectors:
                    detector = self.detectors[detection_type]
                    
                    try:
                        processed_frame, results = detector.predict_video_frame(
                            frame,
                            self.camera.confidence_threshold,
                            self.camera.iou_threshold,
                            self.camera.image_size
                        )
                        
                        for r in results:
                            if r.boxes is not None and len(r.boxes) > 0:
                                confidences = r.boxes.conf.tolist()
                                if confidences and max(confidences) >= self.camera.confidence_threshold:
                                    detection = {
                                        'type': detection_type,
                                        'confidence': max(confidences),
                                        'timestamp': time.time(),
                                        'camera_id': self.camera.id
                                    }
                                    detections.append(detection)
                                    self.detection_count += 1
                                    
                                    if max(confidences) >= 0.8:
                                        self._create_alert(detection_type, max(confidences))
                        
                        annotated_frame = processed_frame
                        
                    except Exception as e:
                        logger.error(f"Detect error:  ({detection_type}): {e}")
            
            return annotated_frame, detections
            
        except Exception as e:
            logger.error(f"AI detect processing error: {e}")
            return frame, []
    
    def _create_alert(self, alert_type: str, confidence: float):
        try:
            from alerts.models import Alert
            
            recent_time = timezone.now() - timezone.timedelta(minutes=5)
            recent_alert = Alert.objects.filter(
                camera=self.camera,
                alert_type=alert_type,
                detection_time__gte=recent_time
            ).first()
            
            if not recent_alert:
                Alert.objects.create(
                    title=f"{alert_type.replace('_', ' ').title()} detect",
                    description=f"AI detected {alert_type} with {confidence:.2f}.",
                    alert_type=alert_type,
                    severity='high' if confidence >= 0.9 else 'medium',
                    confidence=confidence,
                    camera=self.camera,
                    location=self.camera.location
                )
                logger.info(f"Alert: {alert_type} (Thresould: {confidence:.2f})")
                
        except Exception as e:
            logger.error(f"Alert error: {e}")
    
    def send_frame_to_websocket(self, frame_data: str, metadata: Dict):
        try:
            async_to_sync(self.channel_layer.group_send)(
                self.group_name,
                {
                    'type': 'send_frame',
                    'frame': frame_data,
                    'metadata': metadata
                }
            )
        except Exception as e:
            logger.error(f"WebSocket transform error: {e}")
    
    def cache_frame_to_redis(self, frame_data: str, metadata: Dict):
        try:
            self.redis_client.setex(
                f"frame:{self.session_id}",
                settings.STREAMING_SETTINGS['FRAME_CACHE_TTL'],
                frame_data
            )
            
            self.redis_client.setex(
                f"frame_meta:{self.session_id}",
                settings.STREAMING_SETTINGS['FRAME_CACHE_TTL'],
                json.dumps(metadata)
            )
            
        except Exception as e:
            logger.error(f"Redis cashing error: {e}")
    
    def get_metrics(self) -> Dict:
        current_time = time.time()
        uptime = current_time - self.metrics['start_time']
        
        if uptime > 0:
            self.metrics['fps'] = self.frame_count / uptime
        
        self.metrics['frame_count'] = self.frame_count
        self.metrics['detection_count'] = self.detection_count
        self.metrics['uptime'] = uptime
        
        return self.metrics.copy()


class GStreamerAIStreamer(BaseAIStreamer):
    def __init__(self, camera, session_id: str, group_name: str, detectors: Dict):
        super().__init__(camera, session_id, group_name, detectors)
        self.pipeline = None
        self.appsink = None
        self.loop = None
        self.thread = None
    
    def start(self) -> bool:
        try:
            if not self._create_pipeline():
                return False
            
            self.is_streaming = True
            self.thread = threading.Thread(target=self._run_pipeline)
            self.thread.daemon = True
            self.thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"GStreamer stream start error: {e}")
            return False
    
    def stop(self):
        try:
            self.is_streaming = False
            
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            
            if self.loop:
                self.loop.quit()
                
        except Exception as e:
            logger.error(f"GStreamer stream stop error: {e}")
    
    def _create_pipeline(self) -> bool:
        try:
            if self.camera.stream_url.startswith('rtsp://'):
                pipeline_str = f"""
                    rtspsrc location={self.camera.stream_url} latency=0 buffer-mode=0 !
                    rtph264depay !
                    h264parse !
                    avdec_h264 !
                    videoconvert !
                    videoscale !
                    video/x-raw,format=RGB,width=1280,height=720 !
                    appsink name=sink emit-signals=true max-buffers=1 drop=true
                """
            else:  # HTTP MJPEG
                pipeline_str = f"""
                    souphttpsrc location={self.camera.stream_url} !
                    multipartdemux !
                    jpegdec !
                    videoconvert !
                    videoscale !
                    video/x-raw,format=RGB,width=1280,height=720 !
                    appsink name=sink emit-signals=true max-buffers=1 drop=true
                """
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.appsink = self.pipeline.get_by_name('sink')
            self.appsink.connect('new-sample', self._on_new_sample)
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline generation error: {e}")
            return False
    
    def _run_pipeline(self):
        try:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.loop = GLib.MainLoop()
            self.loop.run()
        except Exception as e:
            logger.error(f"Pipeline excecution error: {e}")
    
    def _on_new_sample(self, appsink):
        try:
            if not self.is_streaming:
                return Gst.FlowReturn.OK
            
            sample = appsink.emit('pull-sample')
            if sample:
                buffer = sample.get_buffer()
                caps = sample.get_caps()
                
                success, map_info = buffer.map(Gst.MapFlags.READ)
                if success:
                    frame_data = self._process_gstreamer_frame(map_info.data, caps)
                    if frame_data:
                        current_time = time.time()
                        self.frame_count += 1
                        
                        metadata = {
                            'timestamp': current_time,
                            'frame_count': self.frame_count,
                            'detection_count': self.detection_count,
                            'session_id': self.session_id
                        }
                        
                        self.cache_frame_to_redis(frame_data, metadata)
                        self.send_frame_to_websocket(frame_data, metadata)
                    
                    buffer.unmap(map_info)
            
        except Exception as e:
            logger.error(f"Sample processing error: {e}")
        
        return Gst.FlowReturn.OK
    
    def _process_gstreamer_frame(self, raw_data, caps) -> Optional[str]:
        try:
            import numpy as np
            import cv2
            
            structure = caps.get_structure(0)
            width = structure.get_int('width')[1]
            height = structure.get_int('height')[1]
            
            frame_array = np.frombuffer(raw_data, dtype=np.uint8)
            frame = frame_array.reshape((height, width, 3))
            
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            processed_frame, detections = self.process_detection(frame_bgr)
            
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), settings.GSTREAMER_SETTINGS['JPEG_QUALITY']]
            success, buffer = cv2.imencode('.jpg', processed_frame, encode_param)
            
            if success:
                return base64.b64encode(buffer).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
        
        return None


class OpenCVAIStreamer(BaseAIStreamer):
    
    def __init__(self, camera, session_id: str, group_name: str, detectors: Dict):
        super().__init__(camera, session_id, group_name, detectors)
        self.cap = None
        self.thread = None
    
    def start(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(self.camera.stream_url)
            
            if not self.cap.isOpened():
                logger.error(f"Camera connection failed: {self.camera.stream_url}")
                return False
            
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, settings.GSTREAMER_SETTINGS['DEFAULT_FPS'])
            
            self.is_streaming = True
            
            self.thread = threading.Thread(target=self._process_frames)
            self.thread.daemon = True
            self.thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"OpenCV stream start error: {e}")
            return False
    
    def stop(self):
        try:
            self.is_streaming = False
            
            if self.cap:
                self.cap.release()
                
        except Exception as e:
            logger.error(f"OpenCV stream stop error: {e}")
    
    def _process_frames(self):
        frame_interval = 1.0 / settings.GSTREAMER_SETTINGS['DEFAULT_FPS']
        
        while self.is_streaming and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Frame reading failed!")
                    continue
                
                current_time = time.time()
                if current_time - self.last_frame_time < frame_interval:
                    continue
                
                self.last_frame_time = current_time
                self.frame_count += 1
                
                height, width = frame.shape[:2]
                if width > settings.GSTREAMER_SETTINGS['DEFAULT_WIDTH']:
                    scale = settings.GSTREAMER_SETTINGS['DEFAULT_WIDTH'] / width
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                processed_frame, detections = self.process_detection(frame)
                
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), settings.GSTREAMER_SETTINGS['JPEG_QUALITY']]
                success, buffer = cv2.imencode('.jpg', processed_frame, encode_param)
                
                if success:
                    frame_data = base64.b64encode(buffer).decode('utf-8')
                    
                    metadata = {
                        'timestamp': current_time,
                        'frame_count': self.frame_count,
                        'detection_count': self.detection_count,
                        'session_id': self.session_id,
                        'detections': detections
                    }
                    
                    self.cache_frame_to_redis(frame_data, metadata)
                    
                    self.send_frame_to_websocket(frame_data, metadata)
                
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Frame processing error: {e}")
                time.sleep(0.1)

stream_manager = IntegratedStreamManager()