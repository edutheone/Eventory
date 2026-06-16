from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_user_avatar_user_avatar_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='mpesa_display_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='user',
            name='mpesa_paybill',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='user',
            name='mpesa_till',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='user',
            name='mpesa_pochi',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='user',
            name='mpesa_send_money',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
