from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Alert
from notifications.models import NotificationLog, NotificationSetting
from django.conf import settings
from django.core.mail import send_mail
import logging

logger = logging.getLogger('security_ai')

@receiver(post_save, sender=Alert)
def send_alert_notifications(sender, instance, created, **kwargs):
    """Send notifications when a new alert is created."""
    if created:
        try:
            # Get the camera owner
            if instance.camera:
                user = instance.camera.user
                
                # Get user's notification settings
                try:
                    notification_settings = NotificationSetting.objects.get(user=user)
                except NotificationSetting.DoesNotExist:
                    logger.warning(f"No notification settings found for user {user.id}")
                    return
                
                # Check if notifications are enabled for this alert type
                should_send_email = False
                should_send_sms = False
                should_send_push = False
                
                if instance.alert_type == 'fire_smoke':
                    should_send_email = notification_settings.email_enabled and notification_settings.email_for_fire_smoke
                    should_send_sms = notification_settings.sms_enabled and notification_settings.sms_for_fire_smoke
                    should_send_push = notification_settings.push_enabled and notification_settings.push_for_fire_smoke
                elif instance.alert_type == 'fall':
                    should_send_email = notification_settings.email_enabled and notification_settings.email_for_fall
                    should_send_sms = notification_settings.sms_enabled and notification_settings.sms_for_fall
                    should_send_push = notification_settings.push_enabled and notification_settings.push_for_fall
                elif instance.alert_type == 'violence':
                    should_send_email = notification_settings.email_enabled and notification_settings.email_for_violence
                    should_send_sms = notification_settings.sms_enabled and notification_settings.sms_for_violence
                    should_send_push = notification_settings.push_enabled and notification_settings.push_for_violence
                elif instance.alert_type == 'choking':
                    should_send_email = notification_settings.email_enabled and notification_settings.email_for_choking
                    should_send_sms = notification_settings.sms_enabled and notification_settings.sms_for_choking
                    should_send_push = notification_settings.push_enabled and notification_settings.push_for_choking
                elif instance.alert_type == 'unauthorized_face':
                    should_send_email = notification_settings.email_enabled and notification_settings.email_for_unauthorized_face
                    should_send_sms = notification_settings.sms_enabled and notification_settings.sms_for_unauthorized_face
                    should_send_push = notification_settings.push_enabled and notification_settings.push_for_unauthorized_face
                
                # Check severity threshold
                severity_rank = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
                alert_severity_rank = severity_rank.get(instance.severity, 2)  # default to medium
                
                # Compare with user thresholds
                email_threshold_rank = severity_rank.get(notification_settings.min_severity_email, 2)
                sms_threshold_rank = severity_rank.get(notification_settings.min_severity_sms, 3)
                push_threshold_rank = severity_rank.get(notification_settings.min_severity_push, 2)
                
                should_send_email = should_send_email and (alert_severity_rank >= email_threshold_rank)
                should_send_sms = should_send_sms and (alert_severity_rank >= sms_threshold_rank)
                should_send_push = should_send_push and (alert_severity_rank >= push_threshold_rank)
                
                # Check quiet hours
                if notification_settings.quiet_hours_enabled:
                    current_time = timezone.now().time()
                    start_time = notification_settings.quiet_hours_start
                    end_time = notification_settings.quiet_hours_end
                    
                    # Check if current time is within quiet hours
                    if start_time <= end_time:  # Normal case (e.g., 22:00 to 07:00)
                        if start_time <= current_time <= end_time:
                            # In quiet hours, only send for critical alerts
                            if instance.severity != 'critical':
                                should_send_email = False
                                should_send_sms = False
                                should_send_push = False
                    else:  # Overnight case (e.g., 22:00 to 07:00)
                        if not (end_time <= current_time <= start_time):
                            # In quiet hours, only send for critical alerts
                            if instance.severity != 'critical':
                                should_send_email = False
                                should_send_sms = False
                                should_send_push = False
                
                # Prepare notification content
                camera_name = instance.camera.name if instance.camera else "Unknown camera"
                location = instance.location or "Unknown location"
                
                title = f"ALERT: {instance.get_alert_type_display()} detected"
                message = f"{instance.get_alert_type_display()} detected at {camera_name} ({location}) with {instance.confidence:.2f} confidence."
                
                # Send email notification
                if should_send_email:
                    try:
                        notification_log = NotificationLog.objects.create(
                            user=user,
                            title=title,
                            message=message,
                            notification_type='email',
                            alert=instance,
                            status='pending'
                        )
                        
                        send_mail(
                            subject=title,
                            message=message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[user.email],
                            fail_silently=False,
                        )
                        
                        notification_log.status = 'sent'
                        notification_log.sent_at = timezone.now()
                        notification_log.save()
                        
                        logger.info(f"Email notification sent for alert {instance.id} to {user.email}")
                    except Exception as e:
                        logger.error(f"Error sending email notification: {str(e)}")
                        if notification_log:
                            notification_log.status = 'failed'
                            notification_log.error_message = str(e)
                            notification_log.save()
                
                # Send SMS notification
                if should_send_sms and user.phone_number:
                    # In a real implementation, integrate with SMS service like Twilio
                    notification_log = NotificationLog.objects.create(
                        user=user,
                        title=title,
                        message=message,
                        notification_type='sms',
                        alert=instance,
                        status='pending'
                    )
                    
                    try:
                        # Simulate SMS sending
                        logger.info(f"SMS notification would be sent to {user.phone_number}: {message}")
                        
                        notification_log.status = 'sent'
                        notification_log.sent_at = timezone.now()
                        notification_log.save()
                    except Exception as e:
                        logger.error(f"Error sending SMS notification: {str(e)}")
                        notification_log.status = 'failed'
                        notification_log.error_message = str(e)
                        notification_log.save()
                
                # Send push notification
                if should_send_push:
                    # In a real implementation, integrate with push notification service
                    notification_log = NotificationLog.objects.create(
                        user=user,
                        title=title,
                        message=message,
                        notification_type='push',
                        alert=instance,
                        status='pending'
                    )
                    
                    try:
                        # Simulate push notification
                        logger.info(f"Push notification would be sent to {user.email}: {message}")
                        
                        notification_log.status = 'sent'
                        notification_log.sent_at = timezone.now()
                        notification_log.save()
                    except Exception as e:
                        logger.error(f"Error sending push notification: {str(e)}")
                        notification_log.status = 'failed'
                        notification_log.error_message = str(e)
                        notification_log.save()
            
        except Exception as e:
            logger.error(f"Error in alert notification signal: {str(e)}")