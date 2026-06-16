import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0003_normalize_ticket_type'),
        ('reviews', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventreview',
            name='ticket',
            field=models.ForeignKey(
                blank=True,
                help_text='Ticket that verified attendance for this review.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviews',
                to='bookings.ticket',
            ),
        ),
    ]
