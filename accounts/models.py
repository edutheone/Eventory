from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('attendee', 'Attendee'),
        ('organizer', 'Event Organizer'),
        ('admin', 'Administrator'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='attendee')
    phone = models.CharField(max_length=15, blank=True)
    organization_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    google_id = models.CharField(max_length=128, blank=True, default='')
    location = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True, default='')
    
    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        if self.avatar_url:
            return self.avatar_url
        return ''
    
    # Organizer settings fields
    website = models.URLField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    account_holder = models.CharField(max_length=150, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)

    # M-Pesa payment profile (organizer)
    mpesa_display_name = models.CharField(max_length=150, blank=True)
    mpesa_paybill = models.CharField(max_length=20, blank=True)
    mpesa_till = models.CharField(max_length=20, blank=True)
    mpesa_pochi = models.CharField(max_length=20, blank=True)
    mpesa_send_money = models.CharField(max_length=20, blank=True)

    def has_mpesa_payment_config(self):
        return bool(
            self.mpesa_display_name.strip()
            and any([
                self.mpesa_paybill.strip(),
                self.mpesa_till.strip(),
                self.mpesa_pochi.strip(),
                self.mpesa_send_money.strip(),
            ])
        )

    def mpesa_payment_options(self):
        options = []
        if self.mpesa_paybill.strip():
            options.append({'type': 'paybill', 'label': 'Paybill', 'value': self.mpesa_paybill.strip()})
        if self.mpesa_till.strip():
            options.append({'type': 'till', 'label': 'Till Number', 'value': self.mpesa_till.strip()})
        if self.mpesa_pochi.strip():
            options.append({'type': 'pochi', 'label': 'Pochi la Biashara', 'value': self.mpesa_pochi.strip()})
        if self.mpesa_send_money.strip():
            options.append({'type': 'send_money', 'label': 'Send Money', 'value': self.mpesa_send_money.strip()})
        return options
    
    class Meta(AbstractUser.Meta):
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"


class TeamMember(models.Model):
    id = models.CharField(max_length=8, unique=True, primary_key=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_members_rel')
    email = models.EmailField()
    role = models.CharField(max_length=20, default='viewer')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['organizer']),
            models.Index(fields=['email']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organizer', 'email'],
                name='unique_team_member_per_organizer_email',
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.role}) - Org: {self.organizer.username}"


class ApiKey(models.Model):
    id = models.CharField(max_length=8, unique=True, primary_key=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys_rel')
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['organizer']),
            models.Index(fields=['key']),
        ]

    def __str__(self):
        return f"{self.name} - Org: {self.organizer.username}"


class APIToken(models.Model):
    TOKEN_TYPE_CHOICES = (
        ('access', 'Access'),
        ('refresh', 'Refresh'),
    )

    user = models.ForeignKey(User, related_name='api_tokens', on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    token_type = models.CharField(max_length=10, choices=TOKEN_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['token_hash', 'token_type']),
            models.Index(fields=['user', 'token_type']),
        ]

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()


class AdminNotificationState(models.Model):
    """
    Tracks read/dismissed state for dynamically generated admin notifications.

    Intentionally has no FK — admin notifications are computed at runtime from
    events/tickets/users; this table only stores per-key UI state (see admin_store.py).
    """
    notification_key = models.CharField(max_length=64, unique=True, db_index=True)
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_dismissed']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return self.notification_key
