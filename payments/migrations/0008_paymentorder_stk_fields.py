from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0007_alter_payment_checkout_request_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentorder',
            name='payment_rail',
            field=models.CharField(
                choices=[('manual', 'Manual M-Pesa'), ('stk_platform', 'Platform STK Push')],
                default='manual',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='paymentorder',
            name='checkout_request_id',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='paymentorder',
            name='merchant_request_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='paymentorder',
            name='mpesa_receipt',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='paymentorder',
            name='payer_phone',
            field=models.CharField(blank=True, max_length=15),
        ),
        migrations.AddField(
            model_name='paymentorder',
            name='stk_status',
            field=models.CharField(
                blank=True,
                choices=[('initiated', 'Initiated'), ('success', 'Success'), ('failed', 'Failed')],
                max_length=20,
            ),
        ),
    ]
