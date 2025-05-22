import os
import time
import cv2
import numpy as np
from datetime import datetime
import uuid
import logging
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from alerts.models import Alert
from cameras.models import Camera
from utils.model_manager import ModelManager

logger = logging.getLogger('security_ai')

class VideoProcessor:
    """Handles video processing operations"""
    
    def __init__(self, model_manager=None):
        """Initialize the video processor with the model manager"""
        self.model_manager = model_manager or ModelManager()
        self.output_dir = os.path.join(settings.MEDIA_ROOT, 'alerts', 'videos')
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def process_video(self, video_path, detector_key, conf_threshold, iou_threshold, image_size, camera_id=None):
        """
        Process a video file using the specified detector.
        Returns the path to the processed video file and created alert.
        """
        detector = self.model_manager.get_detector(detector_key)
        
        try:
            # Open the video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video file: {video_path}")
                raise ValueError(f"Failed to open video file: {video_path}")
                
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.info(f"Processing video: {video_path}")
            logger.info(f"Video properties: {width}x{height}, {total_frames} frames, {fps} FPS")
            
            # Create output file name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"{detector_key}_{timestamp}_{uuid.uuid4().hex[:8]}.mp4"
            output_path = os.path.join(self.output_dir, video_filename)
            
            # Define codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # Create an alert record
            camera = None
            location = None
            
            if camera_id:
                try:
                    camera = Camera.objects.get(id=camera_id)
                    location = camera.location
                except Camera.DoesNotExist:
                    logger.warning(f"Camera with ID {camera_id} not found.")
            
            alert = Alert.objects.create(
                title=f"{detector.name} Detection",
                description=f"Automatic detection of {detector.name.lower()} in video.",
                alert_type=detector_key,
                severity='medium',  # Default severity
                camera=camera,
                location=location,
                video_file=f"alerts/videos/{video_filename}"
            )
            
            # Variables for detection tracking
            detection_frames = []
            detection_confidences = []
            
            # Process each frame
            frame_count = 0
            detection_count = 0
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                
                # Process every 5th frame to speed things up
                if frame_count % 5 == 0:
                    try:
                        # Process the frame
                        annotated_frame, results = detector.predict_video_frame(
                            frame, conf_threshold, iou_threshold, image_size
                        )
                        
                        # Check if any detections with required confidence
                        has_detection = False
                        confidence = 0.0
                        
                        for r in results:
                            if r.boxes is not None and len(r.boxes) > 0:
                                # Get the confidences
                                confidences = r.boxes.conf.tolist()
                                
                                if confidences:
                                    max_conf = max(confidences)
                                    if max_conf >= conf_threshold:
                                        has_detection = True
                                        confidence = max(confidence, max_conf)
                                        detection_frames.append(frame_count)
                                        detection_confidences.append(max_conf)
                                        detection_count += 1
                        
                        # Write the annotated frame
                        out.write(annotated_frame)
                        
                        # If we have a detection, update the alert
                        if has_detection and confidence > alert.confidence:
                            alert.confidence = confidence
                            
                            # Adjust severity based on confidence
                            if confidence >= 0.9:
                                alert.severity = 'critical'
                            elif confidence >= 0.7:
                                alert.severity = 'high'
                            elif confidence >= 0.5:
                                alert.severity = 'medium'
                            else:
                                alert.severity = 'low'
                                
                            alert.save(update_fields=['confidence', 'severity'])
                            
                    except Exception as e:
                        logger.error(f"Error processing frame {frame_count}: {str(e)}")
                        # Write the original frame
                        out.write(frame)
                else:
                    # Write the original frame
                    out.write(frame)
                    
            # Release resources
            cap.release()
            out.release()
            
            # Update the alert with detection statistics
            if detection_count > 0:
                description = f"Detected {detector.name.lower()} in {detection_count} frames. "
                description += f"Average confidence: {sum(detection_confidences) / len(detection_confidences):.2f}."
                
                alert.description = description
                alert.save(update_fields=['description'])
                
                # Create thumbnail from a frame with detection
                if detection_frames:
                    # Use the frame with highest confidence for thumbnail
                    best_frame_idx = detection_confidences.index(max(detection_confidences))
                    best_frame = detection_frames[best_frame_idx]
                    
                    # Extract the thumbnail
                    self._create_thumbnail(video_path, alert, best_frame)
            else:
                # No detections found
                alert.status = 'false_positive'
                alert.description = f"No {detector.name.lower()} detected in the video."
                alert.save(update_fields=['status', 'description'])
            
            logger.info(f"Video processing complete. Output saved to: {output_path}")
            return output_path, alert
            
        except Exception as e:
            logger.error(f"Error in video processing: {str(e)}")
            raise
    
    def process_camera_stream(self, camera_id, detector_key, duration=60, frame_limit=300):
        """
        Process a stream from a camera for a specified duration or frame limit.
        Returns the path to the processed video file and created alert.
        """
        try:
            # Get the camera
            camera = Camera.objects.get(id=camera_id)
            
            # Get the detector
            detector = self.model_manager.get_detector(detector_key)
            
            # Get detector config
            config = self.model_manager.get_detector_config(detector_key)
            conf_threshold = config['conf_threshold']
            iou_threshold = config['iou_threshold']
            image_size = config['image_size']
            
            # Get the stream URL
            stream_url = camera.get_stream_url()
            
            # Open the stream
            cap = cv2.VideoCapture(stream_url)
            if not cap.isOpened():
                logger.error(f"Failed to open camera stream: {stream_url}")
                camera.status = 'offline'
                camera.save(update_fields=['status', 'updated_at'])
                raise ValueError(f"Failed to open camera stream: {stream_url}")
            
            # Update camera status
            camera.status = 'online'
            camera.last_online = timezone.now()
            camera.save(update_fields=['status', 'last_online', 'updated_at'])
            
            # Get stream properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 10  # Default FPS if not available
                
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Create output file name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"camera_{camera_id}_{detector_key}_{timestamp}.mp4"
            output_path = os.path.join(self.output_dir, video_filename)
            
            # Define codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # Create an alert record
            alert = Alert.objects.create(
                title=f"{detector.name} Detection - {camera.name}",
                description=f"Real-time detection of {detector.name.lower()} from camera {camera.name}.",
                alert_type=detector_key,
                severity='medium',  # Default severity
                camera=camera,
                location=camera.location,
                video_file=f"alerts/videos/{video_filename}"
            )
            
            # Variables for detection tracking
            frame_count = 0
            detection_count = 0
            detection_frames = []
            detection_confidences = []
            
            # Process frames for the specified duration
            start_time = time.time()
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                
                # Process every nth frame to reduce processing load
                if frame_count % camera.frame_rate == 0:
                    try:
                        # Process the frame
                        annotated_frame, results = detector.predict_video_frame(
                            frame, conf_threshold, iou_threshold, image_size
                        )
                        
                        # Check if any detections with required confidence
                        has_detection = False
                        confidence = 0.0
                        
                        for r in results:
                            if r.boxes is not None and len(r.boxes) > 0:
                                # Get the confidences
                                confidences = r.boxes.conf.tolist()
                                
                                if confidences:
                                    max_conf = max(confidences)
                                    if max_conf >= conf_threshold:
                                        has_detection = True
                                        confidence = max(confidence, max_conf)
                                        detection_frames.append(frame_count)
                                        detection_confidences.append(max_conf)
                                        detection_count += 1
                        
                        # Write the annotated frame
                        out.write(annotated_frame)
                        
                        # If we have a detection, update the alert
                        if has_detection and confidence > alert.confidence:
                            alert.confidence = confidence
                            
                            # Adjust severity based on confidence
                            if confidence >= 0.9:
                                alert.severity = 'critical'
                            elif confidence >= 0.7:
                                alert.severity = 'high'
                            elif confidence >= 0.5:
                                alert.severity = 'medium'
                            else:
                                alert.severity = 'low'
                                
                            alert.save(update_fields=['confidence', 'severity'])
                            
                    except Exception as e:
                        logger.error(f"Error processing frame {frame_count}: {str(e)}")
                        # Write the original frame
                        out.write(frame)
                else:
                    # Write the original frame
                    out.write(frame)
                
                # Check if we've processed enough frames or reached the time limit
                elapsed_time = time.time() - start_time
                if elapsed_time >= duration or frame_count >= frame_limit:
                    break
            
            # Release resources
            cap.release()
            out.release()
            
            # Update the alert with detection statistics
            if detection_count > 0:
                description = f"Detected {detector.name.lower()} in {detection_count} frames. "
                description += f"Average confidence: {sum(detection_confidences) / len(detection_confidences):.2f}."
                
                alert.description = description
                alert.save(update_fields=['description'])
                
                # Create thumbnail from a frame with detection
                if detection_frames:
                    # Use the frame with highest confidence for thumbnail
                    best_frame_idx = detection_confidences.index(max(detection_confidences))
                    
                    # Extract the thumbnail
                    # In this case, we need to create it from the output video
                    self._create_thumbnail_from_output(output_path, alert, detection_frames[best_frame_idx])
            else:
                # No detections found
                alert.status = 'false_positive'
                alert.description = f"No {detector.name.lower()} detected in the camera stream."
                alert.save(update_fields=['status', 'description'])
            
            logger.info(f"Camera stream processing complete. Output saved to: {output_path}")
            return output_path, alert
            
        except Camera.DoesNotExist:
            logger.error(f"Camera with ID {camera_id} not found.")
            raise ValueError(f"Camera with ID {camera_id} not found.")
        except Exception as e:
            logger.error(f"Error in camera stream processing: {str(e)}")
            raise
    
    def _create_thumbnail(self, video_path, alert, frame_number):
        """Create a thumbnail from a specific frame in the video"""
        try:
            cap = cv2.VideoCapture(video_path)
            
            # Seek to the specific frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            
            # Read the frame
            ret, frame = cap.read()
            if not ret:
                logger.error(f"Failed to read frame {frame_number} for thumbnail.")
                cap.release()
                return
            
            # Generate thumbnail path
            thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'alerts', 'thumbnails')
            if not os.path.exists(thumbnail_dir):
                os.makedirs(thumbnail_dir)
                
            thumbnail_filename = f"thumb_{os.path.basename(alert.video_file).split('.')[0]}.jpg"
            thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
            
            # Resize the frame to create a thumbnail
            height, width = frame.shape[:2]
            max_dim = 400
            if height > width:
                new_height = max_dim
                new_width = int(width * (max_dim / height))
            else:
                new_width = max_dim
                new_height = int(height * (max_dim / width))
                
            thumbnail = cv2.resize(frame, (new_width, new_height))
            
            # Save the thumbnail
            cv2.imwrite(thumbnail_path, thumbnail)
            
            # Update the alert with the thumbnail path
            alert.thumbnail = f"alerts/thumbnails/{thumbnail_filename}"
            alert.save(update_fields=['thumbnail'])
            
            cap.release()
            
        except Exception as e:
            logger.error(f"Error creating thumbnail: {str(e)}")
    
    def _create_thumbnail_from_output(self, video_path, alert, frame_number):
        """Create a thumbnail from a specific frame in the output video"""
        self._create_thumbnail(video_path, alert, frame_number)