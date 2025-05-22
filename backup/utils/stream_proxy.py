# utils/stream_proxy.py

import os
import threading
import subprocess
import logging
import time
import signal
import tempfile
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

class StreamProxy:
    """
    Class for proxying video streams to web-friendly formats (HLS/DASH)
    using FFmpeg.
    """
    
    def __init__(self, camera):
        """
        Initialize the stream proxy
        
        Args:
            camera: Camera model instance
        """
        self.camera = camera
        self.process = None
        self.is_running = False
        self.output_dir = os.path.join(settings.MEDIA_ROOT, 'streams', str(camera.id))
        self.stop_event = threading.Event()
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
    
    def cleanup_stream_files(self, camera):
        try:
            stream_dir = os.path.join(settings.MEDIA_ROOT, 'streams', str(camera.id))
            if os.path.exists(stream_dir):
                for filename in os.listdir(stream_dir):
                    file_path = os.path.join(stream_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path}: {e}")
               
                # shutil.rmtree(stream_dir)
        except Exception as e:
            logger.error(f"Error cleaning up stream files: {e}")
    
    def start(self):
        """
        Start the stream proxy
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        try:
            # Stop existing process if running
            self.stop()
            
            # for file in os.listdir(self.output_dir):
            #     file_path = os.path.join(self.output_dir, file)
            #     if os.path.isfile(file_path):
            #         os.unlink(file_path)
            
            # Prepare input URL based on camera type
            input_url = self._get_input_url()
            return {
                    'success': True,
                    'message': 'Stream proxy stoped successfully'
                }
            
            # Prepare FFmpeg command for HLS streaming
            cmd = [
                'ffmpeg',
                '-i', input_url,                 # Input stream
                '-c:v', 'libx264',               # Video codec
                '-preset', 'veryfast',           # Encoding preset
                '-tune', 'zerolatency',          # Tuning for low latency
                '-sc_threshold', '0',            # Disable scene change detection
                '-g', '30',                      # GOP size (1 second at 30 fps)
                '-hls_time', '2',                # Segment length in seconds
                '-hls_list_size', '5',           # Number of segments in playlist
                '-hls_flags', 'delete_segments', # Delete old segments
                '-hls_segment_type', 'mpegts',   # Segment type
                '-hls_segment_filename', f"{self.output_dir}/segment_%03d.ts", # Segment filename pattern
                '-f', 'hls',                     # Output format (HLS)
                f"{self.output_dir}/index.m3u8"  # Output playlist
            ]
            
            # Start FFmpeg process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Wait a moment to see if process starts successfully
            time.sleep(2)
            
            # Check if process is still running
            if self.process.poll() is None:
                self.is_running = True
                
                # Start background thread to monitor process
                self._start_monitor_thread()
                
                logger.info(f"Stream proxy started for camera {self.camera.id}")
                return {
                    'success': True,
                    'message': 'Stream proxy started successfully'
                }
            else:
                stderr = self.process.stderr.read()
                logger.error(f"Failed to start stream proxy: {stderr}")
                return {
                    'success': False,
                    'message': f"Stream proxy start failed: {stderr}"
                }
            
        except Exception as e:
            logger.error(f"Error starting stream proxy: {str(e)}")
            self.stop()
            return {
                'success': False,
                'message': f"Error starting stream proxy: {str(e)}"
            }
    
    def stop(self):
        try:
            processes = subprocess.check_output(['ps', 'aux']).decode()
            for line in processes.split('\n'):
                if 'ffmpeg' in line and str(self.camera.id) in line:
                    pid = line.split()[1]
                    try:
                        subprocess.run(['kill', '-9', pid])
                        logger.info(f"Terminated FFmpeg process for camera {self.camera.id}")
                    except Exception as e:
                        logger.error(f"Error terminating process: {e}")
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.cleanup_stream_files(self.camera)
            
            self.is_running = False
            self.process = None
            
        except Exception as e:
            logger.error(f"Error stopping stream proxy: {e}")
    
    def _get_input_url(self):
        """
        Get the input URL for FFmpeg based on camera type
        
        Returns:
            str: Input URL
        """
        # For RTSP cameras
        if self.camera.stream_url:
            stream_url = self.camera.stream_url
            return stream_url
        
        # # For video files
        # elif self.camera.camera_type == 'file':
        #     file_path = self.camera.url
            
        #     # Check if the file exists
        #     if not os.path.isfile(file_path):
        #         # If not absolute path, check in media directory
        #         media_path = os.path.join(settings.MEDIA_ROOT, file_path)
        #         if os.path.isfile(media_path):
        #             file_path = media_path
            
        #     return file_path
        
        else:
            raise ValueError(f"Unsupported camera URL: {self.camera.stream_url}")
    
    def _start_monitor_thread(self):
        """
        Start a background thread to monitor the FFmpeg process
        """
        def monitor_process():
            while not self.stop_event.is_set():
                # Check if process is still running
                if self.process.poll() is not None:
                    # Process has exited
                    stderr = self.process.stderr.read()
                    if stderr:
                        logger.error(f"Stream proxy exited: {stderr}")
                    else:
                        logger.info(f"Stream proxy exited for camera {self.camera.id}")
                    
                    self.is_running = False
                    break
                
                # Sleep for a bit
                time.sleep(5)
        
        # Start the monitor thread
        monitor_thread = threading.Thread(target=monitor_process)
        monitor_thread.daemon = True
        monitor_thread.start()