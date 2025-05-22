#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'security_ai_system.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    # Create necessary directories if they don't exist
    BASE_DIR = Path(__file__).resolve().parent
    media_dir = BASE_DIR / 'media'
    models_dir = BASE_DIR / 'models'
    logs_dir = BASE_DIR / 'logs'
    
    for directory in [media_dir, models_dir, logs_dir]:
        if not directory.exists():
            directory.mkdir(parents=True)
    
    # Create media subdirectories
    for subdir in ['alerts/videos', 'alerts/thumbnails', 'faces/images', 'faces/verification']:
        dir_path = media_dir / subdir
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()