from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """Serializer for user objects."""
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'username',
                  'phone_number', 'profile_picture', 'date_joined', 'last_login')
        read_only_fields = ('id', 'date_joined', 'last_login')
        
class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user creation."""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    # password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'full_name', 
                  'role', 'username',
                  'phone_number')
        extra_kwargs = {
            'full_name': {'required': True},
            'email': {'required': True}
        }
    
    # def validate(self, attrs):
    #     """Validate that the passwords match."""
    #     if attrs['password'] != attrs['password_confirm']:
    #         raise serializers.ValidationError({"password": "Password fields didn't match."})
    #     return attrs
    
    def create(self, validated_data):
        """Create and return a new user."""
        # Remove password_confirm from the data
        # validated_data.pop('password_confirm')
        
        user = User.objects.create_user(**validated_data)
        return user

class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user details."""
    
    class Meta:
        model = User
        fields = ('full_name', 'phone_number', 'profile_picture')

class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """Validate that the new passwords match."""
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs

class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)