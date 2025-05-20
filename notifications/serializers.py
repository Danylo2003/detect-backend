from rest_framework import serializers
from .models import NotificationSetting, NotificationLog

class NotificationSettingSerializer(serializers.ModelSerializer):
    """Serializer for notification settings."""
    
    class Meta:
        model = NotificationSetting
        exclude = ('user', 'created_at', 'updated_at')

class NotificationLogSerializer(serializers.ModelSerializer):
    """Serializer for notification logs."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = NotificationLog
        fields = '__all__'
        read_only_fields = ('id', 'user', 'created_at', 'sent_at')

class TestNotificationSerializer(serializers.Serializer):
    """Serializer for sending test notifications."""
    
    notification_type = serializers.ChoiceField(
        choices=['email', 'sms', 'push'],
        default='email'
    )
    message = serializers.CharField(
        required=False,
        default="This is a test notification from the Security AI System."
    )