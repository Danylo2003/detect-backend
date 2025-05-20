# utils/face_recognizer.py

import os
import cv2
import numpy as np
import pickle
import logging
from django.conf import settings
from django.db.models import Q
from datetime import datetime

logger = logging.getLogger(__name__)

class FaceRecognizer:
    """
    Class for face recognition operations, including encoding generation,
    face matching, and verification.
    """
    
    def __init__(self):
        """Initialize the face recognizer"""
        # Face detection model file paths
        self.face_detection_model_path = os.path.join(
            settings.MODELS_DIR, 'face_detection', 'face_detection.xml'
        )
        
        # Load face detector
        self._load_face_detector()
    
    def _load_face_detector(self):
        """Load face detection model"""
        try:
            # Check if model file exists
            if not os.path.exists(self.face_detection_model_path):
                logger.error(f"Face detection model not found: {self.face_detection_model_path}")
                self.face_detector = None
                return
            
            # Use OpenCV's Haar cascade for face detection
            self.face_detector = cv2.CascadeClassifier(self.face_detection_model_path)
            
            # Test if model loaded successfully
            if self.face_detector.empty():
                logger.error("Failed to load face detection model")
                self.face_detector = None
            else:
                logger.info("Face detection model loaded successfully")
                
        except Exception as e:
            logger.error(f"Error loading face detection model: {str(e)}")
            self.face_detector = None
    
    def generate_encoding(self, image_path):
        """
        Generate face encoding from an image file
        
        Args:
            image_path: Path to the image file
            
        Returns:
            bytes: Serialized face encoding or None if no face found
        """
        try:
            # Check if face detector is available
            if self.face_detector is None:
                logger.error("Face detector not available")
                return None
            
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return None
            
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            if len(faces) == 0:
                logger.warning(f"No faces detected in image: {image_path}")
                return None
            
            # Use the largest face
            largest_face = max(faces, key=lambda x: x[2] * x[3])
            x, y, w, h = largest_face
            
            # Extract face region
            face_region = image[y:y+h, x:x+w]
            
            # Resize to a standard size
            face_resized = cv2.resize(face_region, (128, 128))
            
            # Convert to grayscale
            face_gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
            
            # Flatten the array
            face_encoding = face_gray.flatten()
            
            # Normalize the encoding
            face_encoding = face_encoding / 255.0
            
            # Serialize the encoding
            encoding_bytes = pickle.dumps(face_encoding)
            
            logger.info(f"Successfully generated face encoding for {image_path}")
            return encoding_bytes
            
        except Exception as e:
            logger.error(f"Error generating face encoding: {str(e)}")
            return None
    
    def compare_faces(self, encoding1, encoding2, threshold=0.6):
        """
        Compare two face encodings
        
        Args:
            encoding1: First face encoding (serialized)
            encoding2: Second face encoding (serialized)
            threshold: Similarity threshold (lower is more strict)
            
        Returns:
            dict: Comparison result with match status and confidence
        """
        try:
            # Deserialize the encodings
            face_encoding1 = pickle.loads(encoding1)
            face_encoding2 = pickle.loads(encoding2)
            
            # Compute Euclidean distance
            distance = np.linalg.norm(face_encoding1 - face_encoding2)
            
            # Convert distance to similarity score (0-1, higher is better)
            # Using a simple conversion where 0 distance = 1.0 similarity
            # and large distances approach 0 similarity
            max_distance = 10.0  # This is a hyperparameter that may need tuning
            similarity = max(0, 1.0 - (distance / max_distance))
            
            # Check if similarity is above threshold
            match = similarity >= threshold
            
            return {
                'match': match,
                'similarity': similarity,
                'distance': distance
            }
            
        except Exception as e:
            logger.error(f"Error comparing faces: {str(e)}")
            return {
                'match': False,
                'similarity': 0.0,
                'distance': float('inf'),
                'error': str(e)
            }
    
    def verify_face(self, image_path, user_id=None, threshold=0.6):
        """
        Verify a face against registered faces
        
        Args:
            image_path: Path to the image file
            user_id: User ID to limit search scope (optional)
            threshold: Similarity threshold
            
        Returns:
            dict: Verification result
        """
        try:
            # Import here to avoid circular imports
            from api.models import AuthorizedFace
            
            # Generate encoding for the input image
            encoding = self.generate_encoding(image_path)
            
            if encoding is None:
                return {
                    'match_found': False,
                    'confidence': 0.0,
                    'face_id': None,
                    'message': "No face detected in the input image"
                }
            
            # Query authorized faces
            query = Q(is_authorized=True)
            
            # Add user filter if provided
            if user_id is not None:
                query &= Q(owner_id=user_id)
            
            # Add validity date filter
            now = datetime.now()
            query &= (Q(valid_until__isnull=True) | Q(valid_until__gt=now))
            
            # Get authorized faces
            faces = AuthorizedFace.objects.filter(query)
            
            # Check each face
            best_match = None
            best_similarity = 0.0
            
            for face in faces:
                # Skip faces without encoding
                if not face.face_encoding:
                    continue
                
                # Compare faces
                result = self.compare_faces(
                    encoding, face.face_encoding, threshold
                )
                
                # Update best match if needed
                if result['match'] and result['similarity'] > best_similarity:
                    best_match = face
                    best_similarity = result['similarity']
            
            if best_match:
                return {
                    'match_found': True,
                    'confidence': best_similarity,
                    'face_id': best_match.id,
                    'message': f"Match found: {best_match.name}"
                }
            else:
                return {
                    'match_found': False,
                    'confidence': best_similarity,
                    'face_id': None,
                    'message': "No match found"
                }
            
        except Exception as e:
            logger.error(f"Error verifying face: {str(e)}")
            return {
                'match_found': False,
                'confidence': 0.0,
                'face_id': None,
                'message': f"Error: {str(e)}"
            }