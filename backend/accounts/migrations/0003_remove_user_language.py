from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_remove_security_login_ip'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='language',
        ),
    ]
