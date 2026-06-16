from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class EventReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_reviews',
    )
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    ticket = models.ForeignKey(
        'bookings.Ticket',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        help_text='Ticket that verified attendance for this review.',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'event'],
                name='unique_review_per_user_event',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} → {self.event_id} ({self.rating}★)'
