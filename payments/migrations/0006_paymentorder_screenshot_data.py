from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_paymentorder_screenshot_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentorder',
            name='screenshot_data',
            field=models.TextField(blank=True, help_text='Base64 data-URI screenshot (serverless-safe storage).'),
        ),
    ]
