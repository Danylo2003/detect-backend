from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthorizedFace(models.Model):
    """Model for storing authorized faces for facial recognition."""
    
    # Basic information
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    # Face image data
    face_image = models.ImageField(upload_to='faces/images/')
    face_encoding = models.BinaryField(blank=True, null=True)  # Store face encoding as binary data
    
    # Additional information
    role = models.CharField(max_length=100, blank=True, null=True)
    access_level = models.CharField(max_length=50, blank=True, null=True)
    
    # Foreign keys
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authorized_faces')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Authorized Face'
        verbose_name_plural = 'Authorized Faces'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class FaceVerificationLog(models.Model):
    """Model for storing face verification logs."""
    
    # Verification result
    authorized_face = models.ForeignKey(
        AuthorizedFace, on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='verification_logs'
    )
    is_match = models.BooleanField(default=False)
    confidence = models.FloatField(default=0.0)
    
    # Source information
    source_image = models.ImageField(upload_to='faces/verification/', blank=True, null=True)
    source_camera = models.ForeignKey(
        'cameras.Camera', on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='face_verifications'
    )
    
    # Timestamp
    verified_at = models.DateTimeField(auto_now_add=True)
    
    # Metadata
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Face Verification Log'
        verbose_name_plural = 'Face Verification Logs'
        ordering = ['-verified_at']
    
    def __str__(self):
        if self.authorized_face:
            return f"Verification of {self.authorized_face.name} at {self.verified_at}"
        return f"Unknown face verification at {self.verified_at}"