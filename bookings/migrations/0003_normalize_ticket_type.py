from django.db import migrations, models


def standard_to_regular(apps, schema_editor):
    Ticket = apps.get_model('bookings', 'Ticket')
    Ticket.objects.filter(ticket_type='Standard').update(ticket_type='Regular')


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_ticket_bookings_ti_status_90f1ac_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(standard_to_regular, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='ticket',
            name='ticket_type',
            field=models.CharField(
                choices=[('Regular', 'Regular'), ('VIP', 'VIP'), ('VVIP', 'VVIP')],
                default='Regular',
                max_length=50,
            ),
        ),
    ]
