from .base_detector import BaseDetector
from django.conf import settings

class FireSmokeDetector(BaseDetector):
    """Detector specialized for fire and smoke detection"""
    
    def __init__(self):
        """Initialize the fire and smoke detector"""
        super().__init__(model_path=settings.MODEL_PATHS['fire_smoke'], name="Fire and Smoke")
    
    def get_description(self):
        """Return a description of the detector"""
        return "Detects fire and smoke in images and videos. Can help in early detection of fire incidents."
    
    def get_model_info(self):
        """Return information about the model used by the detector"""
        return {
            "name": self.name,
            "path": self.model_path,
            "classes": self.class_names,
            "type": "YOLOv8 Object Detection"
        }