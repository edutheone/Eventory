"""
Admin Portal URLs
All admin-related URLs
"""

from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    # Dashboard
    path('', TemplateView.as_view(template_name='admin/dashboard/index.html'), name='admin_portal'),
    path('dashboard/', TemplateView.as_view(template_name='admin/dashboard/index.html'), name='admin_dashboard'),
    
    # Events Management
    path('events/pending/', TemplateView.as_view(template_name='admin/events/pending_approvals.html'), name='admin_pending_approvals'),
    path('events/all/', TemplateView.as_view(template_name='admin/events/all_events.html'), name='admin_all_events'),
    path('events/detail/', TemplateView.as_view(template_name='admin/events/detail.html'), name='admin_event_detail'),
    
    # Bookings Management
    path('bookings/', TemplateView.as_view(template_name='admin/bookings/all_bookings.html'), name='admin_bookings'),
    path('bookings/refunds/', TemplateView.as_view(template_name='admin/bookings/refunds.html'), name='admin_refunds'),
    
    # Users Management
    path('users/', TemplateView.as_view(template_name='admin/users/all_users.html'), name='admin_users'),
    path('users/organizers/', TemplateView.as_view(template_name='admin/users/organizers.html'), name='admin_organizers'),
    path('users/pending-organizers/', TemplateView.as_view(template_name='admin/users/pending_organizers.html'), name='admin_pending_organizers'),
    path('users/detail/', TemplateView.as_view(template_name='admin/users/detail.html'), name='admin_user_detail'),
    
    # Tickets Management
    path('tickets/', TemplateView.as_view(template_name='admin/tickets/all_tickets.html'), name='admin_tickets'),
    path('tickets/scanner/', TemplateView.as_view(template_name='admin/tickets/scanner.html'), name='admin_ticket_scanner'),
    path('tickets/checkin-history/', TemplateView.as_view(template_name='admin/tickets/checkin_history.html'), name='admin_checkin_history'),
    
    # Payments Management
    path('payments/', TemplateView.as_view(template_name='admin/payments/transactions.html'), name='admin_payments'),
    path('payments/payouts/', TemplateView.as_view(template_name='admin/payments/payouts.html'), name='admin_payouts'),
    
    # Reports
    path('reports/', TemplateView.as_view(template_name='admin/reports/analytics.html'), name='admin_reports'),
    path('reports/sales/', TemplateView.as_view(template_name='admin/reports/sales.html'), name='admin_sales_report'),
    path('reports/events/', TemplateView.as_view(template_name='admin/reports/events-report.html'), name='admin_events_report'),
    
    # Notifications
    path('notifications/', TemplateView.as_view(template_name='admin/notifications/index.html'), name='admin_notifications'),
    
    # Support
    path('support/', TemplateView.as_view(template_name='admin/support/tickets.html'), name='admin_support'),
    
    # Profile
    path('profile/', TemplateView.as_view(template_name='admin/profile.html'), name='admin_profile'),
    
    # Settings
    path('settings/general/', TemplateView.as_view(template_name='admin/settings/general.html'), name='admin_general_settings'),
    path('settings/payment/', TemplateView.as_view(template_name='admin/under_construction.html'), name='admin_payment_settings'),
    path('settings/security/', TemplateView.as_view(template_name='admin/under_construction.html'), name='admin_security_settings'),
    
    # Catch-all graceful fallback for unmatched paths in the admin portal
    path('<path:undefined_path>', TemplateView.as_view(template_name='admin/under_construction.html'), name='admin_catch_all'),
]