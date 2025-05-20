from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class NotificationSetting(models.Model):
    """Model for storing user notification preferences."""
    
    # User association
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_settings')
    
    # Email notifications
    email_enabled = models.BooleanField(default=True)
    email_for_fire_smoke = models.BooleanField(default=True)
    email_for_fall = models.BooleanField(default=True)
    email_for_violence = models.BooleanField(default=True)
    email_for_choking = models.BooleanField(default=True)
    email_for_unauthorized_face = models.BooleanField(default=True)
    
    # SMS notifications
    sms_enabled = models.BooleanField(default=False)
    sms_for_fire_smoke = models.BooleanField(default=True)
    sms_for_fall = models.BooleanField(default=True)
    sms_for_violence = models.BooleanField(default=True)
    sms_for_choking = models.BooleanField(default=True)
    sms_for_unauthorized_face = models.BooleanField(default=True)
    
    # Push notifications
    push_enabled = models.BooleanField(default=True)
    push_for_fire_smoke = models.BooleanField(default=True)
    push_for_fall = models.BooleanField(default=True)
    push_for_violence = models.BooleanField(default=True)
    push_for_choking = models.BooleanField(default=True)
    push_for_unauthorized_face = models.BooleanField(default=True)
    
    # Notification schedule
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(default='22:00')
    quiet_hours_end = models.TimeField(default='07:00')
    
    # Severity thresholds
    min_severity_email = models.CharField(
        max_length=20, 
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='medium'
    )
    min_severity_sms = models.CharField(
        max_length=20, 
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='high'
    )
    min_severity_push = models.CharField(
        max_length=20, 
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='medium'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Setting'
        verbose_name_plural = 'Notification Settings'
    
    def __str__(self):
        return f"Notification Settings for {self.user.email}"
    
    @staticmethod
    def get_or_create_settings(user):
        """Get or create notification settings for a user."""
        settings, created = NotificationSetting.objects.get_or_create(user=user)
        return settings


class NotificationLog(models.Model):
    """Model for logging notification events."""
    
    NOTIFICATION_TYPE_CHOICES = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    )
    
    # Basic information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_logs')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Related alert if any
    alert = models.ForeignKey(
        'alerts.Alert', on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='notifications'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Error information
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} to {self.user.email} at {self.created_at}"