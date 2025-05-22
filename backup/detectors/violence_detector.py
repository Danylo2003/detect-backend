from .base_detector import BaseDetector
from django.conf import settings

class ViolenceDetector(BaseDetector):
    """Detector specialized for violence detection"""
    
    def __init__(self):
        """Initialize the violence detector"""
        super().__init__(model_path=settings.MODEL_PATHS['violence'], name="Violence Detection")
    
    def get_description(self):
        """Return a description of the detector"""
        return "Detects violent behaviors and physical altercations in surveillance footage."
    
    def get_model_info(self):
        """Return information about the model used by the detector"""
        return {
            "name": self.name,
            "path": self.model_path,
            "classes": self.class_names,
            "type": "YOLOv8 Object Detection"
        }