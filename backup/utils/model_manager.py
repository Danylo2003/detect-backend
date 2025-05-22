import os
from detectors import FireSmokeDetector, FallDetector, ViolenceDetector, ChokingDetector
from django.conf import settings
import logging

logger = logging.getLogger('security_ai')

class ModelManager:
    """Manages loading and switching between different detector models"""
    
    def __init__(self):
        """Initialize the model manager with all available detectors"""
        self.detectors = {
            "fire_smoke": FireSmokeDetector(),
            "fall": FallDetector(),
            "violence": ViolenceDetector(),
            "choking": ChokingDetector()
        }
        
        # Current active detector
        self.active_detector_key = "fire_smoke"
        
        # Default configuration parameters for each detector
        self.detector_configs = {
            "fire_smoke": {
                "conf_threshold": 0.25,
                "iou_threshold": 0.45,
                "image_size": 640
            },
            "fall": {
                "conf_threshold": 0.4,
                "iou_threshold": 0.37,
                "image_size": 512
            },
            "violence": {
                "conf_threshold": 0.35,
                "iou_threshold": 0.35,
                "image_size": 736
            },
            "choking": {
                "conf_threshold": 0.25,
                "iou_threshold": 0.30,
                "image_size": 640
            }
        }
        
    def get_detector(self, detector_key=None):
        """Get a detector by key, or the active detector if no key is provided"""
        if detector_key is None:
            detector_key = self.active_detector_key
            
        if detector_key not in self.detectors:
            logger.error(f"Unknown detector: {detector_key}")
            raise ValueError(f"Unknown detector: {detector_key}")
            
        return self.detectors[detector_key]
    
    def set_active_detector(self, detector_key):
        """Set the active detector by key"""
        if detector_key not in self.detectors:
            logger.error(f"Unknown detector: {detector_key}")
            raise ValueError(f"Unknown detector: {detector_key}")
            
        self.active_detector_key = detector_key
        return self.get_detector()
    
    def get_available_detectors(self):
        """Get a list of all available detectors"""
        return [
            {
                "key": key,
                "name": detector.name,
                "description": detector.get_description()
            }
            for key, detector in self.detectors.items()
        ]
        
    def get_detector_config(self, detector_key):
        """Get the configuration for a specific detector"""
        if detector_key not in self.detector_configs:
            # Return default config if the detector doesn't have a specific one
            return {
                "conf_threshold": 0.25,
                "iou_threshold": 0.45,
                "image_size": 640
            }
        return self.detector_configs[detector_key]
    
    def update_detector_config(self, detector_key, conf_threshold=None, iou_threshold=None, image_size=None):
        """Update the configuration for a specific detector"""
        if detector_key not in self.detector_configs:
            self.detector_configs[detector_key] = {
                "conf_threshold": 0.25,
                "iou_threshold": 0.45,
                "image_size": 640
            }
            
        # Update only the provided parameters
        if conf_threshold is not None:
            self.detector_configs[detector_key]["conf_threshold"] = conf_threshold
        if iou_threshold is not None:
            self.detector_configs[detector_key]["iou_threshold"] = iou_threshold
        if image_size is not None:
            self.detector_configs[detector_key]["image_size"] = image_size
            
        return self.detector_configs[detector_key]
    
    def validate_models(self):
        """Check if all model files exist"""
        missing_models = []
        for key, detector in self.detectors.items():
            if not os.path.exists(detector.model_path):
                missing_models.append({
                    "key": key,
                    "name": detector.name,
                    "path": detector.model_path
                })
                logger.warning(f"Model file not found: {detector.model_path}")
        
        return {
            "all_valid": len(missing_models) == 0,
            "missing_models": missing_models
        }