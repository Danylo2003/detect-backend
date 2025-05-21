from rest_framework import serializers
from .models import Camera

class CameraSerializer(serializers.ModelSerializer):
    """Serializer for Camera model."""
    
    class Meta:
        model = Camera
        fields = '__all__'
        read_only_fields = ('id', 'user', 'status', 'last_online', 'created_at', 'updated_at')

class CameraCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new camera."""
    class Meta:
        model = Camera
        exclude = ('user', 'status', 'last_online')
    
    def create(self, validated_data):
        """Create and return a new camera instance."""
        user = self.context['request'].user
        camera = Camera.objects.create(user=user, **validated_data)
        
        return camera

class CameraUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating camera details."""
    
    class Meta:
        model = Camera
        exclude = ('user', 'status', 'last_online', 'created_at', 'updated_at')

class CameraStatusSerializer(serializers.ModelSerializer):
    """Serializer for camera status updates."""
    
    class Meta:
        model = Camera
        fields = ('id', 'name', 'status', 'last_online')
        read_only_fields = ('id', 'name')

class CameraListSerializer(serializers.ModelSerializer):
    """Serializer for listing cameras with minimal information."""
    
    class Meta:
        model = Camera
        fields = ('id', 'name', 'location', 'camera_type', 'status', 'last_online')
        read_only_fields = fields

class CameraSettingsSerializer(serializers.ModelSerializer):
    """Serializer for camera detection settings."""
    
    class Meta:
        model = Camera
        fields = (
            'id', 'detection_enabled', 'fire_smoke_detection', 'fall_detection',
            'violence_detection', 'choking_detection', 'face_recognition',
            'confidence_threshold', 'iou_threshold', 'image_size', 'frame_rate'
        )
        read_only_fields = ('id',)