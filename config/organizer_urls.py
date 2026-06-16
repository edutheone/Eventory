from django.urls import path
from django.views.generic import RedirectView, TemplateView

urlpatterns = [
    # Portal root -> dashboard (avoids 404 on /organizer/)
    path('',
         RedirectView.as_view(url='/organizer/dashboard/', permanent=False),
         name='organizer_home'),

    # Login
    path('login/',
         TemplateView.as_view(template_name='shared/auth/login.html'),
         name='organizer_login'),

    # Dashboard
    path('dashboard/',
         TemplateView.as_view(template_name='organizer/dashboard/dashboard.html'),
         name='organizer_dashboard'),

    # Events (list, create, edit, detail)
    path('events/',
         TemplateView.as_view(template_name='organizer/dashboard/events.html'),
         name='organizer_events'),
    path('events/create/',
         TemplateView.as_view(template_name='organizer/dashboard/events.html'),
         name='organizer_events_create'),
    path('events/<int:event_id>/edit/',
         TemplateView.as_view(template_name='organizer/dashboard/events.html'),
         name='organizer_events_edit'),
    path('events/<int:event_id>/',
         TemplateView.as_view(template_name='organizer/dashboard/event_detail.html'),
         name='organizer_event_detail'),

    # Tickets
    path('tickets/',
         TemplateView.as_view(template_name='organizer/dashboard/tickets.html'),
         name='organizer_tickets'),
    path('tickets/scan/',
         TemplateView.as_view(template_name='organizer/dashboard/tickets.html'),
         name='organizer_tickets_scan'),

    # Attendees
    path('attendees/',
         TemplateView.as_view(template_name='organizer/attendees/attendees.html'),
         name='organizer_attendees'),
    path('attendees/<int:attendee_id>/',
         TemplateView.as_view(template_name='organizer/dashboard/attendee_detail.html'),
         name='organizer_attendee_detail'),

    # Bookings
    path('bookings/',
         TemplateView.as_view(template_name='organizer/bookings/bookings.html'),
         name='organizer_bookings'),
    path('bookings/<int:booking_id>/',
         TemplateView.as_view(template_name='organizer/dashboard/booking_detail.html'),
         name='organizer_booking_detail'),



    # Promotions
    path('promotions/',
         TemplateView.as_view(template_name='organizer/dashboard/promotions.html'),
         name='organizer_promotions'),
    path('promotions/create/',
         TemplateView.as_view(template_name='organizer/dashboard/promotions.html'),
         name='organizer_promotions_create'),

    # Reviews
    path('reviews/',
         TemplateView.as_view(template_name='organizer/dashboard/reviews.html'),
         name='organizer_reviews'),

    # Settings
    path('settings/',
         TemplateView.as_view(template_name='organizer/dashboard/settings.html'),
         name='organizer_settings'),
    path('settings/general/',
         TemplateView.as_view(template_name='organizer/dashboard/settings.html'),
         name='organizer_settings_general'),
    path('settings/payment/',
         TemplateView.as_view(template_name='organizer/dashboard/settings.html'),
         name='organizer_settings_payment'),
    path('settings/team/',
         TemplateView.as_view(template_name='organizer/dashboard/settings.html'),
         name='organizer_settings_team'),
    path('settings/api-keys/',
         TemplateView.as_view(template_name='organizer/dashboard/settings.html'),
         name='organizer_settings_api'),

    # Profile (pointing to settings)
    path('profile/',
         TemplateView.as_view(template_name='organizer/settings/settings.html'),
         name='organizer_profile'),

    # FAQs (formerly Support)
    path('faq/',
         TemplateView.as_view(template_name='organizer/dashboard/faq.html'),
         name='organizer_faq'),
    path('support/',
         RedirectView.as_view(url='/organizer/faq/', permanent=True),
         name='organizer_support'),
    path('support/tickets/',
         RedirectView.as_view(url='/organizer/faq/', permanent=True),
         name='organizer_support_tickets'),
    path('support/tickets/<int:ticket_id>/',
         RedirectView.as_view(url='/organizer/faq/', permanent=True),
         name='organizer_support_ticket_detail'),
]