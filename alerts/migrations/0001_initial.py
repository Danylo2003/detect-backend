# Generated by Django 5.2.1 on 2025-05-19 06:14

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cameras', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, null=True)),
                ('alert_type', models.CharField(choices=[('fire_smoke', 'Fire and Smoke'), ('fall', 'Fall Detection'), ('violence', 'Violence'), ('choking', 'Choking'), ('unauthorized_face', 'Unauthorized Face'), ('other', 'Other')], max_length=20)),
                ('status', models.CharField(choices=[('new', 'New'), ('confirmed', 'Confirmed'), ('dismissed', 'Dismissed'), ('false_positive', 'False Positive')], default='new', max_length=20)),
                ('severity', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium', max_length=20)),
                ('confidence', models.FloatField(default=0.0)),
                ('detection_time', models.DateTimeField(auto_now_add=True)),
                ('resolved_time', models.DateTimeField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=200, null=True)),
                ('video_file', models.FileField(blank=True, null=True, upload_to='alerts/videos/')),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='alerts/thumbnails/')),
                ('notes', models.TextField(blank=True, null=True)),
                ('is_test', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('camera', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='cameras.camera')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_alerts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Alert',
                'verbose_name_plural': 'Alerts',
                'ordering': ['-detection_time'],
            },
        ),
    ]
