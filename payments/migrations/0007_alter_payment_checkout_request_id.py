from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0006_paymentorder_screenshot_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='checkout_request_id',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
    ]
