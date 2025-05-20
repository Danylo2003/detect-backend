# utils/notification_service.py (continued)

import logging
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending notifications through various channels
    including email, push notifications, and SMS.
    """
    
    def send_test_notification(self, user, settings, notification_type, message):
        """
        Send a test notification based on type
        
        Args:
            user: User model instance
            settings: User's notification settings
            notification_type: Type of notification ('email', 'push', 'sms', 'all')
            message: Notification message
            
        Returns:
            dict: Result with success status and message
        """
        results = {}
        sent_to = []
        
        try:
            # Send email
            if notification_type in ['email', 'all']:
                email_result = self.send_email(
                    user=user,
                    subject="Test Notification",
                    content=message,
                    template='emails/test_notification.html'
                )
                
                results['email'] = email_result
                if email_result['success']:
                    sent_to.append(f"Email: {user.email}")
            
            # Send push notification
            if notification_type in ['push', 'all']:
                push_result = self.send_push(
                    user=user,
                    title="Test Notification",
                    message=message,
                    data={'type': 'test'}
                )
                
                results['push'] = push_result
                if push_result['success']:
                    sent_to.append("Push notification")
            
            # Send SMS
            if notification_type in ['sms', 'all']:
                sms_result = self.send_sms(
                    user=user,
                    message=f"Test Notification: {message}"
                )
                
                results['sms'] = sms_result
                if sms_result['success']:
                    sent_to.append(f"SMS: {user.phone_number}")
            
            # Check overall success
            success = any(result.get('success', False) for result in results.values())
            
            if success:
                return {
                    'success': True,
                    'message': "Test notification(s) sent successfully",
                    'sent_to': sent_to,
                    'results': results
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to send test notifications",
                    'results': results
                }
            
        except Exception as e:
            logger.error(f"Error sending test notification: {str(e)}")
            return {
                'success': False,
                'message': f"Error sending test notification: {str(e)}"
            }
    
    def send_digest_email(self, user, alert_counts, time_period, date):
        """
        Send a digest email with alert summaries
        
        Args:
            user: User model instance
            alert_counts: Dictionary of alert counts by type
            time_period: Time period ('daily', 'weekly')
            date: Date of the digest
            
        Returns:
            dict: Result with success status and message
        """
        try:
            if not self.email_enabled:
                return {
                    'success': False,
                    'message': "Email notifications are disabled"
                }
            
            if not user.email:
                return {
                    'success': False,
                    'message': "User has no email address"
                }
            
            # Format date
            date_str = date.strftime("%Y-%m-%d")
            
            # Create subject
            if time_period == 'daily':
                subject = f"Daily Alert Digest - {date_str}"
            elif time_period == 'weekly':
                subject = f"Weekly Alert Digest - Week of {date_str}"
            else:
                subject = f"Alert Digest - {date_str}"
            
            # Create plain text content
            text_content = f"Alert Summary for {time_period} digest on {date_str}\n\n"
            
            total_alerts = sum(item['total'] for item in alert_counts.values())
            text_content += f"Total Alerts: {total_alerts}\n\n"
            
            for alert_type, counts in alert_counts.items():
                text_content += f"{alert_type}: {counts['total']} total, {counts['new']} new, {counts['handled']} handled\n"
            
            # Render HTML template
            context = {
                'user': user,
                'alert_counts': alert_counts,
                'time_period': time_period,
                'date': date,
                'total_alerts': total_alerts
            }
            
            html_content = render_to_string('emails/alert_digest.html', context)
            
            # Send email
            send_mail(
                subject=subject,
                message=text_content,
                from_email=self.email_from,
                recipient_list=[user.email],
                html_message=html_content,
                fail_silently=False
            )
            
            logger.info(f"Digest email sent to {user.email}: {subject}")
            
            return {
                'success': True,
                'message': "Digest email sent successfully",
                'recipient': user.email
            }
            
        except Exception as e:
            logger.error(f"Error sending digest email: {str(e)}")
            return {
                'success': False,
                'message': f"Error sending digest email: {str(e)}"
            }