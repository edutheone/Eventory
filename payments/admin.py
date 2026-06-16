from django.contrib import admin
from .models import Payment, PaymentOrder, OrganizerNotification, AttendeeNotification


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'attendee', 'event', 'ticket_type', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'ticket_type')
    search_fields = ('attendee__email', 'event__title', 'submitted_mpesa_name')


admin.site.register(Payment)
admin.site.register(OrganizerNotification)
admin.site.register(AttendeeNotification)
