from .base_detector import BaseDetector
from django.conf import settings

class ChokingDetector(BaseDetector):
    """Detector specialized for choking detection"""
    
    def __init__(self):
        """Initialize the choking detector"""
        super().__init__(model_path=settings.MODEL_PATHS['choking'], name="Choking Detection")
    
    def get_description(self):
        """Return a description of the detector"""
        return "Detects choking incidents to enable rapid response in emergencies."
    
    def get_model_info(self):
        """Return information about the model used by the detector"""
        return {
            "name": self.name,
            "path": self.model_path,
            "classes": self.class_names,
            "type": "YOLOv8 Object Detection"
        }