# security_ai_system/celery.py

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'security_ai_system.settings')

app = Celery('security_ai_system')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Define periodic tasks
app.conf.beat_schedule = {
    'update-camera-statuses': {
        'task': 'api.tasks.update_camera_statuses',
        'schedule': 300.0,  # Every 5 minutes
    },
    'perform-system-check': {
        'task': 'api.tasks.perform_system_check',
        'schedule': 3600.0,  # Every hour
    },
    'send-daily-email-digest': {
        'task': 'api.tasks.send_email_digest',
        'schedule': 86400.0,  # Every day
        'args': (),
        'kwargs': {},
        'options': {'expires': 3600},
    },
}