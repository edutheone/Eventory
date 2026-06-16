from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.core.cache import cache
        cache.clear()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.clear()

class Event(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
        ('sold_out', 'Sold Out'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vip_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vvip_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_seats = models.IntegerField(default=0)
    available_seats = models.IntegerField(default=0)
    
    banner_image = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    attendee_reviews_sent = models.BooleanField(default=False)
    organizer_summary_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['is_featured', 'status']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import uuid
            
            # Generate clean base slug (handling accents, casing, special chars)
            base_slug = slugify(self.title) or "event"
            
            # Truncate base_slug to max 40 chars to ensure suffix fits well under 50 char SlugField limit
            if len(base_slug) > 40:
                base_slug = base_slug[:40].rstrip('-')
                
            slug = base_slug
            while Event.objects.filter(slug=slug).exclude(id=self.id).exists():
                suffix = uuid.uuid4().hex[:4]
                slug = f"{base_slug}-{suffix}"
            self.slug = slug
            
        super().save(*args, **kwargs)
        from django.core.cache import cache
        cache.clear()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.clear()


class EventImage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images')
    image = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.core.cache import cache
        cache.clear()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.clear()

    @property
    def url(self):
        if not self.image:
            return ''
        if self.image.startswith('data:') or self.image.startswith('http://') or self.image.startswith('https://'):
            return self.image
        from django.conf import settings
        if self.image.startswith(settings.MEDIA_URL):
            return self.image
        return settings.MEDIA_URL + self.image

    def __str__(self):
        return f"Image for {self.event.title}"


