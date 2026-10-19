from django.db import migrations, models


def remove_unidentifiable_records(apps, schema_editor):
    SecurityLoginRecord = apps.get_model('accounts', 'SecurityLoginRecord')
    SecurityLoginRecord.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='securityloginrecord',
            name='uniq_user_device_ip_30d',
        ),
        migrations.RemoveField(
            model_name='securityloginrecord',
            name='ip_address',
        ),
        migrations.AddField(
            model_name='securityloginrecord',
            name='session_key',
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.RunPython(
            remove_unidentifiable_records,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='securityloginrecord',
            constraint=models.UniqueConstraint(
                fields=('user', 'device_token_hash', 'session_key'),
                name='uniq_user_device_session',
            ),
        ),
    ]
