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

    def validate_stream_url(self, value):
        """
        Validate that a stream URL is provided and not already registered by the same user.
        """
        if not value:
            raise serializers.ValidationError("A stream URL is required.")
        
        # Check if a camera with this stream URL already exists for this user
        request = self.context.get('request')
        if request and request.user:
            if Camera.objects.filter(user=request.user, stream_url=value).exists():
                raise serializers.ValidationError("This camera is already registered.")
            
        return value
    
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
    def validate_stream_url(self, value):
        """
        Validate that a stream URL is provided and not already registered by another camera
        belonging to the same user.
        """
        if not value:
            raise serializers.ValidationError("A stream URL is required.")
        
        # Check if another camera with this stream URL already exists for this user
        request = self.context.get('request')
        instance = self.instance
        
        if request and request.user and instance:
            # Check if any other camera owned by this user has this URL (exclude current camera)
            if Camera.objects.filter(user=request.user).exclude(id=instance.id).filter(stream_url=value).exists():
                raise serializers.ValidationError("This camera is already registered.")
                
        return value

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