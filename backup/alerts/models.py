from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from cameras.models import Camera

User = get_user_model()

class Alert(models.Model):
    """Alert model for storing detection alerts."""
    
    ALERT_TYPE_CHOICES = (
        ('fire_smoke', 'Fire and Smoke'),
        ('fall', 'Fall Detection'),
        ('violence', 'Violence'),
        ('choking', 'Choking'),
        ('unauthorized_face', 'Unauthorized Face'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('new', 'New'),
        ('confirmed', 'Confirmed'),
        ('dismissed', 'Dismissed'),
        ('false_positive', 'False Positive'),
    )
    
    SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    # Basic information
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    confidence = models.FloatField(default=0.0)
    
    # Detection details
    detection_time = models.DateTimeField(auto_now_add=True)
    resolved_time = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='resolved_alerts'
    )
    
    # Foreign keys
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='alerts')
    
    # Location data
    location = models.CharField(max_length=200, blank=True, null=True)
    
    # Media storage
    video_file = models.FileField(upload_to='alerts/videos/', blank=True, null=True)
    thumbnail = models.ImageField(upload_to='alerts/thumbnails/', blank=True, null=True)
    
    # Metadata
    notes = models.TextField(blank=True, null=True)
    is_test = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-detection_time']
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
    
    def __str__(self):
        return f"{self.get_alert_type_display()} Alert - {self.detection_time}"
    
    def mark_as_confirmed(self, user):
        """Mark the alert as confirmed."""
        self.status = 'confirmed'
        self.resolved_time = timezone.now()
        self.resolved_by = user
        self.save(update_fields=['status', 'resolved_time', 'resolved_by', 'updated_at'])
    
    def mark_as_dismissed(self, user):
        """Mark the alert as dismissed."""
        self.status = 'dismissed'
        self.resolved_time = timezone.now()
        self.resolved_by = user
        self.save(update_fields=['status', 'resolved_time', 'resolved_by', 'updated_at'])
    
    def mark_as_false_positive(self, user):
        """Mark the alert as false positive."""
        self.status = 'false_positive'
        self.resolved_time = timezone.now()
        self.resolved_by = user
        self.save(update_fields=['status', 'resolved_time', 'resolved_by', 'updated_at'])
    
    def add_notes(self, notes):
        """Add notes to the alert."""
        self.notes = notes
        self.save(update_fields=['notes', 'updated_at'])
    
    @property
    def is_resolved(self):
        """Check if the alert is resolved."""
        return self.status in ['confirmed', 'dismissed', 'false_positive']
    
    @property
    def time_since_detection(self):
        """Get the time elapsed since detection."""
        return timezone.now() - self.detection_time