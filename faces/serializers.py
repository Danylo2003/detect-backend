from rest_framework import serializers
from .models import AuthorizedFace, FaceVerificationLog

class AuthorizedFaceSerializer(serializers.ModelSerializer):
    """Serializer for AuthorizedFace model."""
    
    class Meta:
        model = AuthorizedFace
        exclude = ('face_encoding',)
        read_only_fields = ('id', 'user', 'created_at', 'updated_at')

class AuthorizedFaceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new authorized face."""
    
    class Meta:
        model = AuthorizedFace
        fields = ('name', 'description', 'face_image', 'role', 'access_level', 'is_active')
    
    def create(self, validated_data):
        """Create and return a new authorized face."""
        user = self.context['request'].user
        authorized_face = AuthorizedFace.objects.create(user=user, **validated_data)
        return authorized_face

class AuthorizedFaceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating an authorized face."""
    
    class Meta:
        model = AuthorizedFace
        fields = ('name', 'description', 'face_image', 'role', 'access_level', 'is_active')
        
    def validate_face_image(self, value):
        """Validate that a face image is provided if it's being updated."""
        if not value and not self.instance.face_image:
            raise serializers.ValidationError("A face image is required.")
        return value

class FaceVerificationSerializer(serializers.ModelSerializer):
    """Serializer for face verification logs."""
    
    authorized_face_name = serializers.CharField(source='authorized_face.name', read_only=True)
    
    class Meta:
        model = FaceVerificationLog
        fields = '__all__'
        read_only_fields = ('id', 'verified_at')

class FaceVerificationRequestSerializer(serializers.Serializer):
    """Serializer for face verification requests."""
    
    face_image = serializers.ImageField(required=True)
    camera_id = serializers.IntegerField(required=False)
    confidence_threshold = serializers.FloatField(required=False, default=0.6)

class FaceVerificationResponseSerializer(serializers.Serializer):
    """Serializer for face verification responses."""
    
    is_match = serializers.BooleanField()
    confidence = serializers.FloatField()
    matched_face = AuthorizedFaceSerializer(required=False, allow_null=True)
    verification_id = serializers.IntegerField(required=False, allow_null=True)