from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_paymentorder_organizernotification_attendeentification'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentorder',
            name='screenshot_verified',
            field=models.BooleanField(blank=True, help_text='OCR auto-verification result (null = not checked).', null=True),
        ),
    ]
