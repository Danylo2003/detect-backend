# Generated by Django 5.2.1 on 2025-05-19 06:14

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('plan_type', models.CharField(choices=[('free', 'Free'), ('basic', 'Basic'), ('premium', 'Premium'), ('enterprise', 'Enterprise'), ('custom', 'Custom')], max_length=20)),
                ('description', models.TextField(blank=True, null=True)),
                ('max_cameras', models.IntegerField(default=5)),
                ('max_users', models.IntegerField(default=3)),
                ('face_recognition', models.BooleanField(default=False)),
                ('violence_detection', models.BooleanField(default=False)),
                ('storage_days', models.IntegerField(default=30)),
                ('price', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('billing_cycle', models.CharField(choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual'), ('custom', 'Custom')], default='monthly', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Subscription Plan',
                'verbose_name_plural': 'Subscription Plans',
                'ordering': ['price'],
            },
        ),
        migrations.CreateModel(
            name='SystemCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('check_type', models.CharField(max_length=100)),
                ('status', models.CharField(choices=[('success', 'Success'), ('warning', 'Warning'), ('error', 'Error')], max_length=20)),
                ('details', models.TextField(blank=True, null=True)),
                ('cpu_usage', models.FloatField(blank=True, null=True)),
                ('memory_usage', models.FloatField(blank=True, null=True)),
                ('disk_usage', models.FloatField(blank=True, null=True)),
                ('camera_count', models.IntegerField(blank=True, null=True)),
                ('online_cameras', models.IntegerField(blank=True, null=True)),
                ('offline_cameras', models.IntegerField(blank=True, null=True)),
                ('alerts_24h', models.IntegerField(blank=True, null=True)),
                ('processing_fps', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'System Check',
                'verbose_name_plural': 'System Checks',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SystemSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True)),
                ('value', models.TextField()),
                ('description', models.TextField(blank=True, null=True)),
                ('data_type', models.CharField(choices=[('string', 'String'), ('integer', 'Integer'), ('float', 'Float'), ('boolean', 'Boolean'), ('json', 'JSON')], default='string', max_length=20)),
                ('is_editable', models.BooleanField(default=True)),
                ('category', models.CharField(blank=True, max_length=50, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_settings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'System Setting',
                'verbose_name_plural': 'System Settings',
                'ordering': ['category', 'key'],
            },
        ),
        migrations.CreateModel(
            name='UserSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('expired', 'Expired'), ('cancelled', 'Cancelled'), ('pending', 'Pending')], default='active', max_length=20)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('trial_end_date', models.DateField(blank=True, null=True)),
                ('custom_max_cameras', models.IntegerField(blank=True, null=True)),
                ('custom_max_users', models.IntegerField(blank=True, null=True)),
                ('custom_storage_days', models.IntegerField(blank=True, null=True)),
                ('last_payment_date', models.DateField(blank=True, null=True)),
                ('next_payment_date', models.DateField(blank=True, null=True)),
                ('payment_method', models.CharField(blank=True, max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='admin_panel.subscriptionplan')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Subscription',
                'verbose_name_plural': 'User Subscriptions',
                'ordering': ['-start_date'],
            },
        ),
    ]
