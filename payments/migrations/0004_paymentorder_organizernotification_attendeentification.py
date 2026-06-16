import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_ticket_bookings_ti_status_90f1ac_idx_and_more'),
        ('events', '0007_event_events_even_status_ac44c5_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('payments', '0003_remove_payment_legacy_event_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ticket_type', models.CharField(choices=[('Regular', 'Regular'), ('VIP', 'VIP'), ('VVIP', 'VVIP')], default='Regular', max_length=20)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('pending_payment', 'Pending Payment'), ('verifying', 'Verifying Screenshot'), ('manual_review', 'Awaiting Organizer Approval'), ('completed', 'Completed'), ('failed', 'Verification Failed'), ('rejected', 'Rejected')], default='pending_payment', max_length=20)),
                ('screenshot', models.ImageField(blank=True, null=True, upload_to='payment_screenshots/')),
                ('submitted_mpesa_name', models.CharField(blank=True, max_length=150)),
                ('ocr_raw_text', models.TextField(blank=True)),
                ('verification_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attendee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_orders', to=settings.AUTH_USER_MODEL)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_orders', to='events.event')),
                ('organizer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='organizer_payment_orders', to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_orders', to='bookings.ticket')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['status'], name='payments_pa_status_8a1f2c_idx'),
                    models.Index(fields=['attendee', 'status'], name='payments_pa_attende_3b4c5d_idx'),
                    models.Index(fields=['organizer', 'status'], name='payments_pa_organiz_6e7f8a_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='OrganizerNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('notification_type', models.CharField(default='info', max_length=20)),
                ('is_read', models.BooleanField(default=False)),
                ('requires_action', models.BooleanField(default=False)),
                ('action_type', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organizer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='organizer_notifications', to=settings.AUTH_USER_MODEL)),
                ('payment_order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='organizer_notifications', to='payments.paymentorder')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['organizer', 'is_read'], name='payments_or_organiz_9a0b1c_idx')],
            },
        ),
        migrations.CreateModel(
            name='AttendeeNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('notification_type', models.CharField(default='info', max_length=20)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('attendee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendee_notifications', to=settings.AUTH_USER_MODEL)),
                ('payment_order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attendee_notifications', to='payments.paymentorder')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['attendee', 'is_read'], name='payments_at_attende_2d3e4f_idx')],
            },
        ),
    ]
