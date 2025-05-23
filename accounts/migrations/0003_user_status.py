# accounts/migrations/0004_user_status.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_first_name_alter_user_full_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('active', 'Active'),
                    ('blocked', 'Blocked'),
                ],
                default='active',
                help_text='User account status'
            ),
        ),
    ]