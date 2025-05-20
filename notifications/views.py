from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import logging

from .models import NotificationSetting, NotificationLog
from .serializers import (
    NotificationSettingSerializer, NotificationLogSerializer,
    TestNotificationSerializer
)
from utils.permissions import IsOwnerOrAdmin

logger = logging.getLogger('security_ai')

class NotificationSettingViewSet(viewsets.GenericViewSet):
    """ViewSet for managing notification settings."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSettingSerializer
    
    def get_object(self):
        """Get or create notification settings for the current user."""
        return NotificationSetting.get_or_create_settings(self.request.user)
    
    @action(detail=False, methods=['get'])
    def settings(self, request):
        """Get notification preferences."""
        notification_settings = self.get_object()
        serializer = self.get_serializer(notification_settings)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Notification settings retrieved successfully.',
            'errors': []
        })
    
    @action(detail=False, methods=['put', 'patch'])
    def settings(self, request):
        """Update notification preferences."""
        notification_settings = self.get_object()
        
        # Use partial=True to allow partial updates
        serializer = self.get_serializer(
            notification_settings, 
            data=request.data, 
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Notification settings updated successfully.',
            'errors': []
        })
    
    @action(detail=False, methods=['post'])
    def test(self, request):
        """Send a test notification."""
        serializer = TestNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notification_type = serializer.validated_data['notification_type']
        message = serializer.validated_data['message']
        
        # Create a notification log
        notification_log = NotificationLog.objects.create(
            user=request.user,
            title="Test Notification",
            message=message,
            notification_type=notification_type,
            status='pending'
        )
        
        success = False
        error_message = None
        
        try:
            # Handle different notification types
            if notification_type == 'email':
                # Send email notification
                send_mail(
                    subject="Security AI System - Test Notification",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    fail_silently=False,
                )
                success = True
            
            elif notification_type == 'sms':
                # In a real implementation, integrate with SMS service like Twilio
                # For demo purposes, we'll just log it
                logger.info(f"SMS notification would be sent to {request.user.phone_number}: {message}")
                
                if not request.user.phone_number:
                    raise ValueError("No phone number available for SMS notification.")
                
                # Simulate SMS sending success
                success = True
            
            elif notification_type == 'push':
                # In a real implementation, integrate with push notification service
                # For demo purposes, we'll just log it
                logger.info(f"Push notification would be sent to {request.user.email}: {message}")
                
                # Simulate push notification success
                success = True
            
            # Update notification log
            if success:
                notification_log.status = 'sent'
                notification_log.sent_at = timezone.now()
            else:
                notification_log.status = 'failed'
                notification_log.error_message = "Unknown error occurred."
            
            notification_log.save()
            
            return Response({
                'success': True,
                'data': NotificationLogSerializer(notification_log).data,
                'message': f'Test {notification_type} notification sent successfully.',
                'errors': []
            })
            
        except Exception as e:
            logger.error(f"Error sending test notification: {str(e)}")
            
            # Update notification log with error
            notification_log.status = 'failed'
            notification_log.error_message = str(e)
            notification_log.save()
            
            return Response({
                'success': False,
                'data': NotificationLogSerializer(notification_log).data,
                'message': f'Failed to send test {notification_type} notification.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)