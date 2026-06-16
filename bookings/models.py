from django.db import models
from django.contrib.auth import get_user_model
from events.models import Event
import uuid

User = get_user_model()

class Ticket(models.Model):
    STATUS_CHOICES = [
        ('valid', 'Valid'),
        ('checked_in', 'Checked In'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    TICKET_TYPE_CHOICES = [
        ('Regular', 'Regular'),
        ('VIP', 'VIP'),
        ('VVIP', 'VVIP'),
    ]

    ticket_number = models.CharField(max_length=50, unique=True, blank=True)
    attendee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets')
    ticket_type = models.CharField(max_length=50, choices=TICKET_TYPE_CHOICES, default='Regular')
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    billing_name = models.CharField(max_length=150)
    billing_email = models.EmailField()
    billing_phone = models.CharField(max_length=20)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='valid')
    purchase_date = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['purchase_date']),
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = f"TICK-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_number} - {self.event.title}"
