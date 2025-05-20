# Create a new migration file in accounts/migrations/
# For example: accounts/migrations/0002_update_user_model.py

from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Add the new full_name field
        migrations.AddField(
            model_name='user',
            name='full_name',
            field=models.CharField(default='', max_length=150, verbose_name='full name'),
            preserve_default=False,
        ),
        # Migrate existing data (combine first_name and last_name)
        migrations.RunPython(
            code=lambda apps, schema_editor: (
                setattr(
                    user, 
                    'full_name', 
                    f"{user.first_name} {user.last_name}".strip()
                ) or user.save()
                for user in apps.get_model('accounts', 'User').objects.all()
            ),
            reverse_code=lambda apps, schema_editor: (
                setattr(
                    user, 
                    'first_name', 
                    user.full_name.split(' ')[0] if user.full_name else ""
                ) or setattr(
                    user,
                    'last_name',
                    ' '.join(user.full_name.split(' ')[1:]) if user.full_name and ' ' in user.full_name else ""
                ) or user.save()
                for user in apps.get_model('accounts', 'User').objects.all()
            ),
        ),
        # Remove the first_name and last_name fields
        migrations.RemoveField(
            model_name='user',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='user',
            name='last_name',
        ),
    ]