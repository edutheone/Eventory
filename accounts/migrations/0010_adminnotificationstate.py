from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_user_mpesa_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminNotificationState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_key', models.CharField(db_index=True, max_length=64, unique=True)),
                ('is_read', models.BooleanField(default=False)),
                ('is_dismissed', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['is_dismissed'], name='accounts_ad_is_dism_0c0f0d_idx'),
                    models.Index(fields=['is_read'], name='accounts_ad_is_read_8f2a1b_idx'),
                ],
            },
        ),
    ]
