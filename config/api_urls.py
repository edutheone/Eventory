"""
API URLs for EventHub
"""

from django.urls import path
from .urls import (
    api_contact_submit, get_categories_list, newsletter_subscribe,
    dashboard_stats, recent_events, recent_bookings, top_events,
    revenue_chart, categories_chart, events_list_api, categories_list_api,
    users_list_api, user_profile, notifications_api, settings_api,
    analytics_categories, analytics_top_events, analytics_user_growth, analytics_kpi,
    api_pending_events, api_all_events, api_event_detail, api_approve_event,
    api_reject_event, api_delete_event, api_event_history, api_event_stats,
    api_bulk_approve, api_bulk_reject
)

urlpatterns = [
    # Public APIs
    path('contact/submit/', api_contact_submit, name='api_contact_submit'),
    path('events/categories/', get_categories_list, name='api_categories'),
    path('newsletter/subscribe/', newsletter_subscribe, name='newsletter_subscribe'),
    
    # Admin Dashboard APIs
    path('admin/dashboard/stats/', dashboard_stats, name='admin_dashboard_stats'),
    path('admin/events/recent/', recent_events, name='admin_recent_events'),
    path('admin/bookings/recent/', recent_bookings, name='admin_recent_bookings'),
    path('admin/events/top/', top_events, name='admin_top_events'),
    path('admin/charts/revenue/', revenue_chart, name='admin_revenue_chart'),
    path('admin/charts/categories/', categories_chart, name='admin_categories_chart'),
    path('admin/events/', events_list_api, name='admin_events_list'),
    path('admin/categories/', categories_list_api, name='admin_categories_list'),
    path('admin/users/', users_list_api, name='admin_users_list'),
    path('admin/user/profile/', user_profile, name='admin_user_profile'),
    path('admin/notifications/', notifications_api, name='admin_notifications'),
    path('admin/settings/', settings_api, name='admin_settings_api'),
    
    # Analytics APIs
    path('admin/analytics/categories/', analytics_categories, name='analytics_categories'),
    path('admin/analytics/top-events/', analytics_top_events, name='analytics_top_events'),
    path('admin/analytics/user-growth/', analytics_user_growth, name='analytics_user_growth'),
    path('admin/analytics/kpi/', analytics_kpi, name='analytics_kpi'),
    
    # Event Approval APIs
    path('admin/events/pending/', api_pending_events, name='api_pending_events'),
    path('admin/events/all/', api_all_events, name='api_all_events'),
    path('admin/events/<int:event_id>/', api_event_detail, name='api_event_detail'),
    path('admin/events/<int:event_id>/approve/', api_approve_event, name='api_approve_event'),
    path('admin/events/<int:event_id>/reject/', api_reject_event, name='api_reject_event'),
    path('admin/events/<int:event_id>/delete/', api_delete_event, name='api_delete_event'),
    path('admin/events/<int:event_id>/history/', api_event_history, name='api_event_history'),
    path('admin/events/stats/', api_event_stats, name='api_event_stats'),
    path('admin/events/bulk-approve/', api_bulk_approve, name='api_bulk_approve'),
    path('admin/events/bulk-reject/', api_bulk_reject, name='api_bulk_reject'),
]