from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class SystemCheck(models.Model):
    """Model for storing system diagnostics and health checks."""
    
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    )
    
    # Basic information
    check_type = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    details = models.TextField(blank=True, null=True)
    
    # Metrics
    cpu_usage = models.FloatField(blank=True, null=True)
    memory_usage = models.FloatField(blank=True, null=True)
    disk_usage = models.FloatField(blank=True, null=True)
    
    # Camera metrics
    camera_count = models.IntegerField(blank=True, null=True)
    online_cameras = models.IntegerField(blank=True, null=True)
    offline_cameras = models.IntegerField(blank=True, null=True)
    
    # Processing metrics
    alerts_24h = models.IntegerField(blank=True, null=True)
    processing_fps = models.FloatField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'System Check'
        verbose_name_plural = 'System Checks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.check_type} - {self.status} - {self.created_at}"


class SystemSetting(models.Model):
    """Model for storing system-wide settings."""
    
    # Setting key and value
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    
    # Metadata
    description = models.TextField(blank=True, null=True)
    data_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string'
    )
    
    # Usage information
    is_editable = models.BooleanField(default=True)
    category = models.CharField(max_length=50, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Audit fields
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_settings'
    )
    
    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'
        ordering = ['category', 'key']
    
    def __str__(self):
        return f"{self.key} - {self.category}"
    
    def get_typed_value(self):
        """Return the value converted to its appropriate data type."""
        if self.data_type == 'integer':
            return int(self.value)
        elif self.data_type == 'float':
            return float(self.value)
        elif self.data_type == 'boolean':
            return self.value.lower() in ('true', 'yes', '1', 't', 'y')
        elif self.data_type == 'json':
            import json
            return json.loads(self.value)
        return self.value


class SubscriptionPlan(models.Model):
    """Model for storing subscription plan details."""
    
    PLAN_TYPES = (
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
        ('custom', 'Custom'),
    )
    
    BILLING_CYCLES = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
        ('custom', 'Custom'),
    )
    
    # Basic information
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    description = models.TextField(blank=True, null=True)
    
    # Features and limits
    max_cameras = models.IntegerField(default=5)
    max_users = models.IntegerField(default=3)
    face_recognition = models.BooleanField(default=False)
    violence_detection = models.BooleanField(default=False)
    storage_days = models.IntegerField(default=30)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLES, default='monthly')
    
    # Active status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - ${self.price}/{self.billing_cycle}"


class UserSubscription(models.Model):
    """Model for storing user subscription details."""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
    )
    
    # Basic information
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Subscription dates
    start_date = models.DateField()
    end_date = models.DateField()
    trial_end_date = models.DateField(null=True, blank=True)
    
    # Custom limits (overrides plan defaults)
    custom_max_cameras = models.IntegerField(null=True, blank=True)
    custom_max_users = models.IntegerField(null=True, blank=True)
    custom_storage_days = models.IntegerField(null=True, blank=True)
    
    # Payment information
    last_payment_date = models.DateField(null=True, blank=True)
    next_payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name} - {self.status}"
    
    @property
    def is_trial(self):
        """Check if the subscription is in trial period."""
        from django.utils import timezone
        if self.trial_end_date:
            return timezone.now().date() <= self.trial_end_date
        return False
    
    @property
    def is_active(self):
        """Check if the subscription is active."""
        from django.utils import timezone
        return (
            self.status == 'active' and
            timezone.now().date() >= self.start_date and
            timezone.now().date() <= self.end_date
        )
    
    @property
    def max_cameras(self):
        """Get the maximum number of cameras allowed."""
        return self.custom_max_cameras if self.custom_max_cameras is not None else self.plan.max_cameras
    
    @property
    def max_users(self):
        """Get the maximum number of users allowed."""
        return self.custom_max_users if self.custom_max_users is not None else self.plan.max_users
    
    @property
    def storage_days(self):
        """Get the number of days to store recordings."""
        return self.custom_storage_days if self.custom_storage_days is not None else self.plan.storage_days