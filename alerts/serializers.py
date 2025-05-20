from rest_framework import serializers
from .models import Alert
from accounts.serializers import UserSerializer
from cameras.serializers import CameraListSerializer

class AlertSerializer(serializers.ModelSerializer):
    """Serializer for Alert model."""
    
    camera_details = CameraListSerializer(source='camera', read_only=True)
    resolved_by_details = UserSerializer(source='resolved_by', read_only=True)
    
    class Meta:
        model = Alert
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class AlertListSerializer(serializers.ModelSerializer):
    """Serializer for listing alerts with minimal information."""
    
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = Alert
        fields = (
            'id', 'title', 'alert_type', 'status', 'severity',
            'confidence', 'detection_time', 'camera_name',
            'thumbnail'
        )
        read_only_fields = fields

class AlertCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new alert."""
    
    class Meta:
        model = Alert
        fields = (
            'title', 'description', 'alert_type', 'severity',
            'confidence', 'camera', 'location', 'video_file',
            'thumbnail', 'notes', 'is_test'
        )

class AlertStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating alert status."""
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Alert
        fields = ('status', 'notes')
    
    def validate_status(self, value):
        """Validate the status field."""
        valid_statuses = ['confirmed', 'dismissed', 'false_positive']
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Invalid status. Valid choices are: {', '.join(valid_statuses)}"
            )
        return value

class AlertSummarySerializer(serializers.Serializer):
    """Serializer for alert summary statistics."""
    
    total_alerts = serializers.IntegerField()
    new_alerts = serializers.IntegerField()
    confirmed_alerts = serializers.IntegerField()
    dismissed_alerts = serializers.IntegerField()
    false_positive_alerts = serializers.IntegerField()
    
    by_type = serializers.DictField()
    by_severity = serializers.DictField()
    
    daily_count = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField()
        )
    )
    weekly_count = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField()
        )
    )
    monthly_count = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField()
        )
    )