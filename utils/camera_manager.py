# utils/camera_manager.py (continued)

import cv2
import logging
import requests
import time
import threading
import queue
import os
from collections import defaultdict
from django.conf import settings

logger = logging.getLogger(__name__)

class CameraManager:
    """
    Manager class for handling camera operations including connection verification,
    stream management, and status updates.
    """
    
    def __init__(self):
        self.active_streams = {}  # Stream objects indexed by camera_id
        self.stream_locks = defaultdict(threading.Lock)  # Locks for each stream
    
    def verify_camera_connection(self, camera):
        """
        Verify if a camera can be connected to.
        
        Args:
            camera: Camera model instance
            
        Returns:
            dict: Result with success status and message
        """
        try:
            if camera.camera_type == 'rtsp':
                # Verify RTSP connection
                return self._verify_rtsp_connection(camera)
            
            elif camera.camera_type == 'http':
                # Verify HTTP connection (for IP cameras with HTTP streams)
                return self._verify_http_connection(camera)
            
            elif camera.camera_type == 'local':
                # Verify local webcam connection
                return self._verify_local_connection(camera)
            
            elif camera.camera_type == 'file':
                # Verify file exists
                return self._verify_file_connection(camera)
            
            else:
                return {
                    'success': False,
                    'message': f"Unsupported camera type: {camera.camera_type}"
                }
            
        except Exception as e:
            logger.error(f"Error verifying camera connection: {str(e)}")
            return {
                'success': False,
                'message': f"Connection error: {str(e)}"
            }
    
    def get_stream_url(self, camera):
        """
        Get streaming URL for a camera
        
        Args:
            camera: Camera model instance
            
        Returns:
            dict: Result with success status, message, and stream URL if successful
        """
        try:
            # For RTSP cameras, we might need to proxy the stream
            if camera.camera_type == 'rtsp':
                # Start a stream proxy if not already running
                if camera.id not in self.active_streams:
                    proxy_result = self._start_stream_proxy(camera)
                    if not proxy_result['success']:
                        return proxy_result
                
                return {
                    'success': True,
                    'message': 'Stream proxy available',
                    'stream_url': f"/api/stream/{camera.id}/index.m3u8"
                }
            
            # For HTTP cameras, return the direct URL
            elif camera.camera_type == 'http':
                # Check if authentication is needed
                if camera.username and camera.password:
                    # Extract protocol, host, path
                    url_parts = camera.url.split('://', 1)
                    if len(url_parts) > 1:
                        protocol = url_parts[0]
                        rest = url_parts[1].split('/', 1)
                        host = rest[0]
                        path = rest[1] if len(rest) > 1 else ''
                        
                        # Construct URL with embedded credentials
                        stream_url = f"{protocol}://{camera.username}:{camera.password}@{host}/{path}"
                    else:
                        stream_url = camera.url
                else:
                    stream_url = camera.url
                
                return {
                    'success': True,
                    'message': 'Direct stream URL available',
                    'stream_url': stream_url
                }
            
            # For local webcams, we need to proxy the stream
            elif camera.camera_type == 'local':
                # Start a stream proxy if not already running
                if camera.id not in self.active_streams:
                    proxy_result = self._start_stream_proxy(camera)
                    if not proxy_result['success']:
                        return proxy_result
                
                return {
                    'success': True,
                    'message': 'Stream proxy available',
                    'stream_url': f"/api/stream/{camera.id}/index.m3u8"
                }
            
            # For video files, we could serve them directly or via a proxy
            elif camera.camera_type == 'file':
                # Check if file exists
                file_check = self._verify_file_connection(camera)
                if not file_check['success']:
                    return file_check
                
                # Return direct URL to file
                return {
                    'success': True,
                    'message': 'Video file URL available',
                    'stream_url': camera.url if camera.url.startswith('/') else f"/media/{camera.url}"
                }
            
            else:
                return {
                    'success': False,
                    'message': f"Unsupported camera type: {camera.camera_type}"
                }
            
        except Exception as e:
            logger.error(f"Error getting stream URL: {str(e)}")
            return {
                'success': False,
                'message': f"Stream error: {str(e)}"
            }
    
    def update_camera_statuses(self, cameras):
        """
        Update status for multiple cameras
        
        Args:
            cameras: QuerySet of Camera model instances
        """
        for camera in cameras:
            try:
                result = self.verify_camera_connection(camera)
                
                if result['success']:
                    if camera.status != 'online':
                        camera.update_status('online')
                else:
                    if camera.status == 'online':
                        camera.update_status('offline')
            
            except Exception as e:
                logger.error(f"Error updating camera status: {str(e)}")
                camera.update_status('error')
    
    def disconnect_camera(self, camera):
        """
        Properly disconnect a camera and clean up resources
        
        Args:
            camera: Camera model instance
        """
        try:
            # Stop stream proxy if running
            if camera.id in self.active_streams:
                with self.stream_locks[camera.id]:
                    stream = self.active_streams.pop(camera.id)
                    if hasattr(stream, 'stop'):
                        stream.stop()
                    
                    logger.info(f"Disconnected camera {camera.id} - {camera.name}")
            
            # Update status
            camera.update_status('disabled')
            
            return {
                'success': True,
                'message': f"Camera {camera.name} disconnected successfully"
            }
        
        except Exception as e:
            logger.error(f"Error disconnecting camera: {str(e)}")
            return {
                'success': False,
                'message': f"Error disconnecting camera: {str(e)}"
            }
    
    def capture_frame(self, camera):
        """
        Capture a single frame from a camera
        
        Args:
            camera: Camera model instance
            
        Returns:
            dict: Result with success status, message, and frame if successful
        """
        try:
            # For RTSP cameras
            if camera.camera_type == 'rtsp':
                return self._capture_rtsp_frame(camera)
            
            # For HTTP cameras
            elif camera.camera_type == 'http':
                return self._capture_http_frame(camera)
            
            # For local webcams
            elif camera.camera_type == 'local':
                return self._capture_local_frame(camera)
            
            # For video files
            elif camera.camera_type == 'file':
                return self._capture_file_frame(camera)
            
            else:
                return {
                    'success': False,
                    'message': f"Unsupported camera type: {camera.camera_type}",
                    'frame': None
                }
        
        except Exception as e:
            logger.error(f"Error capturing frame: {str(e)}")
            return {
                'success': False,
                'message': f"Error capturing frame: {str(e)}",
                'frame': None
            }
    
    def _verify_rtsp_connection(self, camera):
        """
        Verify RTSP camera connection
        """
        try:
            # Try to open the RTSP stream with a timeout
            url = camera.url
            if camera.username and camera.password:
                # Add authentication to URL if not already included
                if '@' not in url:
                    # Parse URL to extract protocol, host, path
                    url_parts = url.split('://', 1)
                    if len(url_parts) > 1:
                        protocol = url_parts[0]
                        rest = url_parts[1].split('/', 1)
                        host = rest[0]
                        path = rest[1] if len(rest) > 1 else ''
                        
                        # Construct URL with embedded credentials
                        url = f"{protocol}://{camera.username}:{camera.password}@{host}/{path}"
            
            # Set OpenCV to use a short timeout
            os.environ['OPENCV_FFMPEG_READ_TIMEOUT'] = '5'  # 5 seconds timeout
            
            # Open the stream
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            
            # Try to read a frame with timeout
            success = cap.isOpened() and cap.grab()
            
            # Release the stream
            cap.release()
            
            if success:
                return {
                    'success': True,
                    'message': "RTSP connection successful"
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to connect to RTSP stream"
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"RTSP connection error: {str(e)}"
            }
    
    def _verify_http_connection(self, camera):
        """
        Verify HTTP camera connection
        """
        try:
            # Create request with auth if needed
            auth = None
            if camera.username and camera.password:
                auth = (camera.username, camera.password)
            
            # Make request with timeout
            response = requests.get(camera.url, auth=auth, timeout=5, stream=True)
            
            # Check if response is an image or video stream
            content_type = response.headers.get('Content-Type', '')
            
            if response.status_code == 200 and ('image' in content_type or 'video' in content_type):
                return {
                    'success': True,
                    'message': "HTTP connection successful"
                }
            else:
                return {
                    'success': False,
                    'message': f"HTTP connection failed with status {response.status_code}"
                }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': "HTTP connection timed out"
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'message': f"HTTP connection error: {str(e)}"
            }
    
    def _verify_local_connection(self, camera):
        """
        Verify local webcam connection
        """
        try:
            # Get the device index (usually a number like 0, 1, etc.)
            device_index = 0
            if camera.url and camera.url.isdigit():
                device_index = int(camera.url)
            
            # Try to open the webcam
            cap = cv2.VideoCapture(device_index)
            
            # Check if webcam is opened successfully
            if not cap.isOpened():
                cap.release()
                return {
                    'success': False,
                    'message': f"Failed to open webcam at index {device_index}"
                }
            
            # Try to read a frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return {
                    'success': True,
                    'message': "Local webcam connection successful"
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to read frame from webcam"
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"Webcam connection error: {str(e)}"
            }
    
    def _verify_file_connection(self, camera):
        """
        Verify video file connection
        """
        try:
            # Get file path
            file_path = camera.url
            
            # Check if the file exists
            if not os.path.isfile(file_path):
                # If not absolute path, check in media directory
                media_path = os.path.join(settings.MEDIA_ROOT, file_path)
                if not os.path.isfile(media_path):
                    return {
                        'success': False,
                        'message': f"Video file not found: {file_path}"
                    }
                file_path = media_path
            
            # Try to open the video file
            cap = cv2.VideoCapture(file_path)
            
            # Check if file is opened successfully
            if not cap.isOpened():
                cap.release()
                return {
                    'success': False,
                    'message': f"Failed to open video file: {file_path}"
                }
            
            # Try to read a frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return {
                    'success': True,
                    'message': "Video file connection successful"
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to read frame from video file"
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"Video file error: {str(e)}"
            }
    
    def _start_stream_proxy(self, camera):
        """
        Start a stream proxy for the camera
        """
        # This would typically involve starting a process to relay
        # the camera stream to a web-friendly format like HLS or DASH
        # For simplicity, we'll just provide a placeholder implementation
        with self.stream_locks[camera.id]:
            try:
                from utils.stream_proxy import StreamProxy
                
                # Create proxy instance
                proxy = StreamProxy(camera)
                success = proxy.start()
                
                if success:
                    self.active_streams[camera.id] = proxy
                    return {
                        'success': True,
                        'message': "Stream proxy started successfully"
                    }
                else:
                    return {
                        'success': False,
                        'message': "Failed to start stream proxy"
                    }
            
            except Exception as e:
                logger.error(f"Error starting stream proxy: {str(e)}")
                return {
                    'success': False,
                    'message': f"Stream proxy error: {str(e)}"
                }
    
    def _capture_rtsp_frame(self, camera):
        """
        Capture a frame from an RTSP camera
        """
        try:
            # Prepare URL with auth if needed
            url = camera.url
            if camera.username and camera.password:
                # Add authentication to URL if not already included
                if '@' not in url:
                    # Parse URL to extract protocol, host, path
                    url_parts = url.split('://', 1)
                    if len(url_parts) > 1:
                        protocol = url_parts[0]
                        rest = url_parts[1].split('/', 1)
                        host = rest[0]
                        path = rest[1] if len(rest) > 1 else ''
                        
                        # Construct URL with embedded credentials
                        url = f"{protocol}://{camera.username}:{camera.password}@{host}/{path}"
            
            # Set timeout
            os.environ['OPENCV_FFMPEG_READ_TIMEOUT'] = '5'
            
            # Open the stream
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            
            if not cap.isOpened():
                return {
                    'success': False,
                    'message': "Failed to open RTSP stream",
                    'frame': None
                }
            
            # Read a frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return {
                    'success': True,
                    'message': "Frame captured successfully",
                    'frame': frame
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to read frame from RTSP stream",
                    'frame': None
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"RTSP frame capture error: {str(e)}",
                'frame': None
            }
    
    def _capture_http_frame(self, camera):
        """
        Capture a frame from an HTTP camera
        """
        try:
            # Create request with auth if needed
            auth = None
            if camera.username and camera.password:
                auth = (camera.username, camera.password)
            
            # Make request with timeout
            response = requests.get(camera.url, auth=auth, timeout=5, stream=True)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f"HTTP request failed with status {response.status_code}",
                    'frame': None
                }
            
            # Convert response content to image
            import numpy as np
            img_array = np.frombuffer(response.content, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if frame is None:
                return {
                    'success': False,
                    'message': "Failed to decode image from HTTP response",
                    'frame': None
                }
            
            return {
                'success': True,
                'message': "Frame captured successfully",
                'frame': frame
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"HTTP frame capture error: {str(e)}",
                'frame': None
            }
    
    def _capture_local_frame(self, camera):
        """
        Capture a frame from a local webcam
        """
        try:
            # Get the device index
            device_index = 0
            if camera.url and camera.url.isdigit():
                device_index = int(camera.url)
            
            # Open the webcam
            cap = cv2.VideoCapture(device_index)
            
            if not cap.isOpened():
                return {
                    'success': False,
                    'message': f"Failed to open webcam at index {device_index}",
                    'frame': None
                }
            
            # Read a frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return {
                    'success': True,
                    'message': "Frame captured successfully",
                    'frame': frame
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to read frame from webcam",
                    'frame': None
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"Webcam frame capture error: {str(e)}",
                'frame': None
            }
    
    def _capture_file_frame(self, camera):
        """
        Capture a frame from a video file
        """
        try:
            # Get file path
            file_path = camera.url
            
            # Check if the file exists
            if not os.path.isfile(file_path):
                # If not absolute path, check in media directory
                media_path = os.path.join(settings.MEDIA_ROOT, file_path)
                if not os.path.isfile(media_path):
                    return {
                        'success': False,
                        'message': f"Video file not found: {file_path}",
                        'frame': None
                    }
                file_path = media_path
            
            # Open the video file
            cap = cv2.VideoCapture(file_path)
            
            if not cap.isOpened():
                return {
                    'success': False,
                    'message': f"Failed to open video file: {file_path}",
                    'frame': None
                }
            
            # Read a frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return {
                    'success': True,
                    'message': "Frame captured successfully",
                    'frame': frame
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to read frame from video file",
                    'frame': None
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"Video file frame capture error: {str(e)}",
                'frame': None
            }