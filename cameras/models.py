from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Camera(models.Model):
    """Camera model for storing camera information."""
    
    STATUS_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    )
    
    name = models.CharField(max_length=100)
    stream_url = models.CharField(max_length=500)
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    last_online = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Foreign keys
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cameras')
    
    # Detection settings
    detection_enabled = models.BooleanField(default=True)
    fire_smoke_detection = models.BooleanField(default=True)
    fall_detection = models.BooleanField(default=True)
    violence_detection = models.BooleanField(default=True)
    choking_detection = models.BooleanField(default=True)
    face_recognition = models.BooleanField(default=False)
    
    # Performance settings
    confidence_threshold = models.FloatField(default=0.6)
    iou_threshold = models.FloatField(default=0.45)
    image_size = models.IntegerField(default=640)
    frame_rate = models.IntegerField(default=10)  # Process every nth frame
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Camera'
        verbose_name_plural = 'Cameras'
    
    def __str__(self):
        return self.name
    
    def get_stream_url(self):
        """Return the full stream URL with authentication if needed."""
        if self.camera_type == 'rtsp' and self.username and self.password:
            # Parse the URL to insert authentication
            if '://' in self.stream_url:
                protocol, rest = self.stream_url.split('://', 1)
                return f"{protocol}://{self.username}:{self.password}@{rest}"
            return self.stream_url
        return self.stream_url
    
    def update_status(self, status):
        """Update the camera status."""
        self.status = status
        self.save(update_fields=['status', 'updated_at'])