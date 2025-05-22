# streaming/apps.py
from django.apps import AppConfig

class StreamingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'streaming'
    
    def ready(self):
        from .stream_manager import IntegratedStreamManager
        IntegratedStreamManager().start_background_tasks()