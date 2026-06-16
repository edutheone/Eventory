from django.contrib import admin

from .models import EventReview


@admin.register(EventReview)
class EventReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('event__title', 'user__username', 'comment')
