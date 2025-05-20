from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from notifications.models import NotificationSetting

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_notification_settings(sender, instance, created, **kwargs):
    """Create notification settings for new users."""
    if created:
        NotificationSetting.objects.create(user=instance)