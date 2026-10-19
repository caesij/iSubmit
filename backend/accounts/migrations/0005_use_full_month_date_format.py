from django.db import migrations, models


def migrate_abbreviated_date_format(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(date_format='M j, Y').update(date_format='F j, Y')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_date_format'),
    ]

    operations = [
        migrations.RunPython(
            migrate_abbreviated_date_format,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='user',
            name='date_format',
            field=models.CharField(
                choices=[
                    ('F j, Y', 'Full Month DD, YYYY (June 1, 2026)'),
                    ('m/d/Y', 'MM/DD/YYYY'),
                    ('Y-m-d', 'YYYY-MM-DD'),
                ],
                default='F j, Y',
                max_length=10,
            ),
        ),
    ]
