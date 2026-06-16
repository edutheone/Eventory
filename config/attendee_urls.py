"""
Attendee Portal URLs
All attendee-related URLs
"""

from django.urls import path
from django.views.generic import TemplateView

from events.views import homepage_view, success_stories_view

urlpatterns = [
    # Homepage
    path('', homepage_view, name='attendee_home'),
    
    # Auth
    path('login/', TemplateView.as_view(template_name='shared/auth/login.html'), name='attendee_login'),
    
    # Static Pages
    path('about/', TemplateView.as_view(template_name='attendee/pages/about.html'), name='attendee_about'),
    path('contact/', TemplateView.as_view(template_name='attendee/pages/contact.html'), name='attendee_contact'),
    path('faq/', TemplateView.as_view(template_name='attendee/pages/faq.html'), name='attendee_faq'),
    path('help-center/', TemplateView.as_view(template_name='attendee/pages/help-center.html'), name='attendee_help_center'),
    path('how-it-works/', TemplateView.as_view(template_name='attendee/pages/how_it_works.html'), name='attendee_how_it_works'),
    path('privacy/', TemplateView.as_view(template_name='attendee/pages/privacy.html'), name='attendee_privacy'),
    path('terms/', TemplateView.as_view(template_name='attendee/pages/terms.html'), name='attendee_terms'),
    path('reviews/', TemplateView.as_view(template_name='attendee/pages/reviews.html'), name='attendee_reviews'),
    path('success-stories/', success_stories_view, name='attendee_success_stories'),
    path('why-eventhub/', TemplateView.as_view(template_name='attendee/pages/about.html'), name='attendee_why_eventhub'),
    path('customer-stories/', success_stories_view, name='attendee_customer_stories'),
    
    # Events
    path('events/', TemplateView.as_view(template_name='attendee/events/list.html'), name='attendee_events'),
    path('events/detail/', TemplateView.as_view(template_name='attendee/events/detail.html'), name='attendee_event_detail'),
    path('events/search/', TemplateView.as_view(template_name='attendee/events/search.html'), name='attendee_event_search'),
    
    # Dashboard (Protected)
    path('dashboard/', TemplateView.as_view(template_name='attendee/dashboard/dashboard.html'), name='attendee_dashboard'),
    
    # Profile
    path('profile/', TemplateView.as_view(template_name='attendee/pages/profile.html'), name='attendee_profile'),
    
    # Tickets
    path('tickets/', TemplateView.as_view(template_name='attendee/tickets/list.html'), name='attendee_tickets'),
    path('my-tickets/', TemplateView.as_view(template_name='attendee/tickets/list.html'), name='attendee_my_tickets'),
    path('tickets/detail/', TemplateView.as_view(template_name='attendee/tickets/detail.html'), name='attendee_ticket_detail'),
    path('tickets/qr/', TemplateView.as_view(template_name='attendee/tickets/qr.html'), name='attendee_ticket_qr'),
    
    # Bookings
    path('bookings/', TemplateView.as_view(template_name='attendee/bookings/history.html'), name='attendee_bookings'),
    path('bookings/detail/', TemplateView.as_view(template_name='attendee/bookings/detail.html'), name='attendee_booking_detail'),
    
    # Cart & Wishlist
    path('cart/', TemplateView.as_view(template_name='attendee/cart/cart.html'), name='attendee_cart'),
    path('wishlist/', TemplateView.as_view(template_name='attendee/wishlist/wishlist.html'), name='attendee_wishlist'),
    
    # Support
    path('support/', TemplateView.as_view(template_name='attendee/support/tickets.html'), name='attendee_support'),
    
    # Notifications
    path('notifications/', TemplateView.as_view(template_name='attendee/notifications/notifications.html'), name='attendee_notifications'),
    
    # Settings
    path('settings/', TemplateView.as_view(template_name='attendee/settings/settings.html'), name='attendee_settings'),
]
