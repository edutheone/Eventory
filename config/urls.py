"""
Main URL Configuration for EventHub Project
Includes all portal URLs
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.views import LogoutView
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from events.views import (
    organizer_dashboard_stats, organizer_dashboard_revenue, api_event_list, api_category_list, api_event_detail,
    api_dashboard_stats, api_dashboard_recommendations, api_dashboard_recent_activity,
    api_featured_events, api_events_check_expired, homepage_view,
    api_discover_local_events, api_platform_stats, api_db_status, api_run_migrations,
)
from accounts.auth_views import register_submit, login_submit
from bookings.views import (
    ticket_checkout_api, api_tickets_upcoming, api_tickets_past,
    api_ticket_detail, api_ticket_qr, api_ticket_download,
    api_organizer_bookings_list, api_organizer_tickets_list,
    api_organizer_tickets_stats, api_organizer_ticket_verify,
    api_organizer_ticket_checkin, api_organizer_attendees_list,
    api_organizer_attendees_stats
)
from bookings.email_service import send_newsletter_confirmation
from payments.order_views import (
    create_payment_order,
    payment_order_status,
    payment_order_stk_push,
    mpesa_stk_callback,
    verify_screenshot,
    submit_mpesa_name,
    attendee_notifications_list,
    attendee_notification_mark_read,
    attendee_notifications_mark_all_read,
    organizer_notifications_list,
    organizer_notifications_unread,
    organizer_notification_mark_read,
    organizer_notifications_mark_all_read,
    organizer_pending_orders,
    organizer_approve_order,
    organizer_reject_order,
    organizer_payment_order_screenshot,
)
from reviews.views import (
    api_my_reviews,
    api_event_reviews,
    api_create_review,
    api_update_review,
    api_delete_review,
)
from events.api_organizer_views import (
    api_organizer_events_list,
    api_organizer_events_create,
    api_organizer_events_detail,
    api_organizer_events_update,
    api_organizer_events_delete,
    api_organizer_settings_general,
    api_organizer_settings_general_update,
    api_organizer_payouts_settings,
    api_organizer_payouts_settings_update,
    api_organizer_settings_team,
    api_organizer_settings_team_add,
    api_organizer_settings_team_remove,
    api_organizer_settings_apikeys,
    api_organizer_settings_apikeys_create,
    api_organizer_settings_apikeys_revoke,
    api_organizer_settings_mpesa,
    api_organizer_settings_mpesa_update,
    api_organizer_reviews_stats,
    api_organizer_event_analytics,
    api_organizer_upload_image,
    api_organizer_upload_gallery,
    api_organizer_delete_gallery_image
)
import json

# ============ ADMIN LOGIN VIEWS ============

def admin_login_page(request):
    """Admin login page view"""
    return render(request, 'admin/login.html')

def admin_login_submit(request):
    """Process admin login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('/admin-portal/dashboard/')
        else:
            messages.error(request, 'Invalid credentials or you do not have admin access.')
            return redirect('/admin/login/')
    
    return redirect('/admin/login/')

def admin_logout_view(request):
    """Admin logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('/login/')

def user_logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('/login/')

# ============ API VIEWS ============

@csrf_exempt
@require_http_methods(["POST"])
def newsletter_subscribe(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        if email:
            email_sent = send_newsletter_confirmation(email)
            if email_sent:
                return JsonResponse({'success': True, 'message': 'Subscribed successfully!'})
            else:
                return JsonResponse({'success': True, 'message': 'Subscribed successfully, but failed to send email.'})
        return JsonResponse({'success': False, 'message': 'Email required'}, status=400)
    except:
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def api_contact_submit(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()
        
        if not name or len(name) < 2:
            return JsonResponse({'success': False, 'message': 'Name must be at least 2 characters'}, status=400)
        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required'}, status=400)
        if not message or len(message) < 10:
            return JsonResponse({'success': False, 'message': 'Message must be at least 10 characters'}, status=400)
        
        return JsonResponse({'success': True, 'message': 'Thank you! We will get back to you soon.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_categories_list(request):
    categories_data = [
        {'id': 1, 'name': 'Music', 'event_count': 3, 'icon': 'music'},
        {'id': 2, 'name': 'Technology', 'event_count': 2, 'icon': 'microchip'},
        {'id': 3, 'name': 'Business', 'event_count': 1, 'icon': 'briefcase'},
        {'id': 4, 'name': 'Sports', 'event_count': 1, 'icon': 'futbol'},
        {'id': 5, 'name': 'Arts', 'event_count': 1, 'icon': 'palette'},
        {'id': 6, 'name': 'Food', 'event_count': 1, 'icon': 'utensils'},
    ]
    return JsonResponse({'success': True, 'categories': categories_data})

# ============ ADMIN API ENDPOINTS ============

from accounts import admin_api


# ============ MAIN URL PATTERNS ============

urlpatterns = [
    # Django Admin
    path('django-admin/', admin.site.urls),
    
    # Admin Login URLs
    path('admin/login/', admin_login_page, name='admin_login'),
    path('admin/login/submit/', admin_login_submit, name='admin_login_submit'),
    path('admin/logout/', admin_logout_view, name='admin_logout'),
    
    # Shared Auth Pages
    path('login/', TemplateView.as_view(template_name='shared/auth/login.html'), name='login'),
    path('login/submit/', login_submit, name='login_submit'),
    path('register/', TemplateView.as_view(template_name='shared/auth/register.html'), name='register'),
    path('register/submit/', register_submit, name='register_submit'),
    path('forgot-password/', TemplateView.as_view(template_name='shared/auth/forgot_password.html'), name='forgot_password'),
    path('reset-password/', TemplateView.as_view(template_name='shared/auth/reset_password.html'), name='reset_password'),
    path('2fa/', TemplateView.as_view(template_name='shared/auth/2fa.html'), name='two_factor'),
    path('verify-email/', TemplateView.as_view(template_name='shared/auth/email_verify.html'), name='verify_email'),
    path('logout/', user_logout_view, name='logout'),
    
    # Static Pages (Homepage)
    path('', homepage_view, name='home'),
    
    # API Endpoints
    path('api/', include('accounts.urls')),
    path('api/attendee/', include('accounts.urls')),
    path('api/attendee/events/', api_event_list, name='api_attendee_event_list'),
    path('api/attendee/events/featured/', api_featured_events, name='api_attendee_events_featured'),
    path('api/attendee/events/search/', api_event_list, name='api_attendee_event_search'),
    path('api/attendee/events/categories/', api_category_list, name='api_attendee_category_list'),
    path('api/attendee/categories/', api_category_list, name='api_attendee_category_list_legacy'),
    path('api/attendee/events/<int:event_id>/', api_event_detail, name='api_attendee_event_detail'),
    path('api/attendee/events/<int:event_id>/reviews/', api_event_reviews, name='api_attendee_event_reviews'),
    path('api/attendee/reviews/', api_my_reviews, name='api_attendee_my_reviews'),
    path('api/attendee/reviews/create/<int:event_id>/', api_create_review, name='api_attendee_create_review'),
    path('api/attendee/reviews/update/<int:review_id>/', api_update_review, name='api_attendee_update_review'),
    path('api/attendee/reviews/delete/<int:review_id>/', api_delete_review, name='api_attendee_delete_review'),
    path('api/attendee/dashboard/stats/', api_dashboard_stats, name='api_attendee_dashboard_stats'),
    path('api/attendee/dashboard/recommendations/', api_dashboard_recommendations, name='api_attendee_dashboard_recommendations'),
    path('api/attendee/dashboard/recent-activity/', api_dashboard_recent_activity, name='api_attendee_dashboard_recent_activity'),
    path('api/attendee/tickets/upcoming/', api_tickets_upcoming, name='api_attendee_tickets_upcoming'),
    path('api/attendee/tickets/past/', api_tickets_past, name='api_attendee_tickets_past'),
    path('api/attendee/tickets/<str:ticket_number>/', api_ticket_detail, name='api_attendee_ticket_detail'),
    path('api/attendee/tickets/<str:ticket_number>/qr/', api_ticket_qr, name='api_attendee_ticket_qr'),
    path('api/attendee/tickets/<str:ticket_number>/download/', api_ticket_download, name='api_attendee_ticket_download'),
    
    # Organizer API Endpoints
    path('api/organizer/', include('accounts.urls')),
    path('api/organizer/dashboard/stats/', organizer_dashboard_stats, name='organizer_dashboard_stats'),
    path('api/organizer/dashboard/revenue/', organizer_dashboard_revenue, name='organizer_dashboard_revenue'),
    path('api/organizer/events/', api_organizer_events_list, name='api_organizer_events_list'),
    path('api/organizer/events/create/', api_organizer_events_create, name='api_organizer_events_create'),
    path('api/organizer/events/<int:event_id>/', api_organizer_events_detail, name='api_organizer_events_detail'),
    path('api/organizer/events/<int:event_id>/analytics/', api_organizer_event_analytics, name='api_organizer_event_analytics'),
    path('api/organizer/events/<int:event_id>/upload-image/', api_organizer_upload_image, name='api_organizer_upload_image'),
    path('api/organizer/events/<int:event_id>/upload-gallery/', api_organizer_upload_gallery, name='api_organizer_upload_gallery'),
    path('api/organizer/events/<int:event_id>/gallery/<int:image_id>/delete/', api_organizer_delete_gallery_image, name='api_organizer_delete_gallery_image'),
    path('api/organizer/events/<int:event_id>/update/', api_organizer_events_update, name='api_organizer_events_update'),
    path('api/organizer/events/<int:event_id>/delete/', api_organizer_events_delete, name='api_organizer_events_delete'),
    path('api/organizer/bookings/', api_organizer_bookings_list, name='api_organizer_bookings_list'),
    path('api/organizer/tickets/', api_organizer_tickets_list, name='api_organizer_tickets_list'),
    path('api/organizer/tickets/stats/', api_organizer_tickets_stats, name='api_organizer_tickets_stats'),
    path('api/organizer/tickets/stats/<int:event_id>/', api_organizer_tickets_stats, name='api_organizer_tickets_stats_event'),
    path('api/organizer/tickets/<str:ticket_number>/verify/', api_organizer_ticket_verify, name='api_organizer_ticket_verify'),
    path('api/organizer/tickets/<str:ticket_number>/checkin/', api_organizer_ticket_checkin, name='api_organizer_ticket_checkin'),
    path('api/organizer/attendees/', api_organizer_attendees_list, name='api_organizer_attendees_list'),
    path('api/organizer/attendees/stats/', api_organizer_attendees_stats, name='api_organizer_attendees_stats'),
    path('api/organizer/reviews/stats/', api_organizer_reviews_stats, name='api_organizer_reviews_stats'),
    
    # Organizer Settings Endpoints
    path('api/organizer/settings/general/', api_organizer_settings_general, name='api_organizer_settings_general'),
    path('api/organizer/settings/general/update/', api_organizer_settings_general_update, name='api_organizer_settings_general_update'),
    path('api/organizer/payouts/settings/', api_organizer_payouts_settings, name='api_organizer_payouts_settings'),
    path('api/organizer/payouts/settings/update/', api_organizer_payouts_settings_update, name='api_organizer_payouts_settings_update'),
    path('api/organizer/settings/team/', api_organizer_settings_team, name='api_organizer_settings_team'),
    path('api/organizer/settings/team/add/', api_organizer_settings_team_add, name='api_organizer_settings_team_add'),
    path('api/organizer/settings/team/<str:member_id>/remove/', api_organizer_settings_team_remove, name='api_organizer_settings_team_remove'),
    path('api/organizer/settings/api-keys/', api_organizer_settings_apikeys, name='api_organizer_settings_apikeys'),
    path('api/organizer/settings/api-keys/create/', api_organizer_settings_apikeys_create, name='api_organizer_settings_apikeys_create'),
    path('api/organizer/settings/api-keys/<str:key_id>/revoke/', api_organizer_settings_apikeys_revoke, name='api_organizer_settings_apikeys_revoke'),
    path('api/organizer/settings/mpesa/', api_organizer_settings_mpesa, name='api_organizer_settings_mpesa'),
    path('api/organizer/settings/mpesa/update/', api_organizer_settings_mpesa_update, name='api_organizer_settings_mpesa_update'),

    # Manual M-Pesa payment orders
    path('api/attendee/payment-orders/create/', create_payment_order, name='create_payment_order'),
    path('api/attendee/payment-orders/<int:order_id>/status/', payment_order_status, name='payment_order_status'),
    path('api/attendee/payment-orders/<int:order_id>/stk-push/', payment_order_stk_push, name='payment_order_stk_push'),
    path('api/payments/mpesa/stk-callback/', mpesa_stk_callback, name='mpesa_stk_callback'),
    path('api/attendee/payment-orders/<int:order_id>/verify-screenshot/', verify_screenshot, name='verify_screenshot'),
    path('api/attendee/payment-orders/<int:order_id>/submit-mpesa-name/', submit_mpesa_name, name='submit_mpesa_name'),
    path('api/attendee/notifications/', attendee_notifications_list, name='attendee_notifications_list'),
    path('api/attendee/notifications/<int:notification_id>/read/', attendee_notification_mark_read, name='attendee_notification_mark_read'),
    path('api/attendee/notifications/mark-all-read/', attendee_notifications_mark_all_read, name='attendee_notifications_mark_all_read'),
    path('api/organizer/notifications/', organizer_notifications_list, name='organizer_notifications_list'),
    path('api/organizer/notifications/unread/', organizer_notifications_unread, name='organizer_notifications_unread'),
    path('api/organizer/notifications/<int:notification_id>/read/', organizer_notification_mark_read, name='organizer_notification_mark_read'),
    path('api/organizer/notifications/mark-all-read/', organizer_notifications_mark_all_read, name='organizer_notifications_mark_all_read'),
    path('api/organizer/payment-orders/pending/', organizer_pending_orders, name='organizer_pending_orders'),
    path('api/organizer/payment-orders/<int:order_id>/approve/', organizer_approve_order, name='organizer_approve_order'),
    path('api/organizer/payment-orders/<int:order_id>/reject/', organizer_reject_order, name='organizer_reject_order'),
    path('api/organizer/payment-orders/<int:order_id>/screenshot/', organizer_payment_order_screenshot, name='organizer_payment_order_screenshot'),
    
    path('api/bookings/checkout/', ticket_checkout_api, name='ticket_checkout_api'),
    path('api/contact/submit/', api_contact_submit, name='api_contact_submit'),
    path('api/events/categories/', get_categories_list, name='api_categories'),
    path('newsletter/subscribe/', newsletter_subscribe, name='newsletter_subscribe'),
    path('api/events/check-expired/', api_events_check_expired, name='api_events_check_expired'),
    path('api/events/discover/', api_discover_local_events, name='api_events_discover'),
    path('api/platform/stats/', api_platform_stats, name='api_platform_stats'),
    # ============ ADMIN PORTAL API ENDPOINTS ============
    # Dashboard
    path('api/admin/dashboard/stats/', admin_api.dashboard_stats, name='admin_dashboard_stats'),
    path('api/admin/dashboard/revenue-chart/', admin_api.revenue_chart, name='admin_revenue_chart'),
    path('api/admin/dashboard/category-chart/', admin_api.categories_chart, name='admin_categories_chart'),
    path('api/admin/dashboard/recent-activity/', admin_api.recent_activity, name='admin_recent_activity'),
    path('api/admin/dashboard/top-events/', admin_api.top_events, name='admin_top_events'),
    path('api/admin/dashboard/pending-count/', admin_api.pending_count, name='admin_pending_count'),

    # Events Management
    path('api/admin/events/', admin_api.events_list_api, name='admin_events_list'),
    path('api/admin/events/pending/', admin_api.api_pending_events, name='api_pending_events'),
    path('api/admin/events/pending/count/', admin_api.pending_count, name='admin_pending_count_legacy'),
    path('api/admin/events/stats/', admin_api.api_event_stats, name='admin_event_stats'),
    path('api/admin/categories/', admin_api.categories_list_api, name='admin_categories_list'),
    path('api/admin/events/list/', admin_api.events_upcoming_api, name='admin_events_list_select'),
    path('api/admin/events/upcoming/', admin_api.events_upcoming_api, name='admin_events_upcoming_select'),
    path('api/admin/events/export/', admin_api.api_events_export, name='admin_events_export'),
    path('api/admin/events/<int:event_id>/', admin_api.api_event_detail, name='api_event_detail'),
    path('api/admin/events/<int:event_id>/approve/', admin_api.api_approve_event, name='api_approve_event'),
    path('api/admin/events/<int:event_id>/reject/', admin_api.api_reject_event, name='api_reject_event'),
    path('api/admin/events/<int:event_id>/delete/', admin_api.api_delete_event, name='api_delete_event'),
    path('api/admin/events/<int:event_id>/history/', admin_api.api_event_history, name='api_event_history'),
    path('api/admin/events/bulk-approve/', admin_api.api_bulk_approve, name='api_bulk_approve'),
    path('api/admin/events/bulk-reject/', admin_api.api_bulk_reject, name='api_bulk_reject'),

    # Bookings Management
    path('api/admin/bookings/', admin_api.bookings_list_api, name='admin_bookings_list'),
    path('api/admin/bookings/stats/', admin_api.bookings_stats, name='admin_bookings_stats'),
    path('api/admin/bookings/export/', admin_api.bookings_export, name='admin_bookings_export'),
    path('api/admin/bookings/<str:booking_id>/', admin_api.booking_detail, name='admin_booking_detail'),
    path('api/admin/bookings/<str:booking_id>/refund/', admin_api.booking_refund, name='admin_booking_refund'),
    path('api/admin/bookings/<str:booking_id>/cancel/', admin_api.booking_cancel, name='admin_booking_cancel'),

    # Refunds Management
    path('api/admin/refunds/', admin_api.refunds_list_api, name='admin_refunds_list'),
    path('api/admin/refunds/stats/', admin_api.refunds_stats, name='admin_refunds_stats'),
    path('api/admin/refunds/export/', admin_api.refunds_export, name='admin_refunds_export'),
    path('api/admin/refunds/<int:refund_id>/', admin_api.refund_detail_api, name='admin_refund_detail'),
    path('api/admin/refunds/<int:refund_id>/approve/', admin_api.refund_approve_api, name='admin_refund_approve'),
    path('api/admin/refunds/<int:refund_id>/reject/', admin_api.refund_reject_api, name='admin_refund_reject'),

    # Users Management
    path('api/admin/users/', admin_api.users_list_api, name='admin_users_list'),
    path('api/admin/users/stats/', admin_api.users_stats, name='admin_users_stats'),
    path('api/admin/users/export/', admin_api.users_export, name='admin_users_export'),
    path('api/admin/users/<int:user_id>/', admin_api.user_detail_api, name='admin_user_detail'),
    path('api/admin/users/<int:user_id>/reset-password/', admin_api.user_reset_password, name='admin_user_reset_password'),
    path('api/admin/users/<int:user_id>/suspend/', admin_api.user_suspend, name='admin_user_suspend'),
    path('api/admin/users/<int:user_id>/activate/', admin_api.user_activate, name='admin_user_activate'),
    path('api/admin/users/<int:user_id>/reactivate/', admin_api.user_activate, name='admin_user_reactivate'),

    # Organizer Management
    path('api/admin/organizers/stats/', admin_api.organizers_stats_api, name='admin_organizers_stats'),
    path('api/admin/organizers/verified/', admin_api.organizers_verified_api, name='admin_organizers_verified'),
    path('api/admin/organizers/suspended/', admin_api.organizers_suspended_api, name='admin_organizers_suspended'),
    path('api/admin/organizers/pending/stats/', admin_api.organizers_pending_stats_api, name='admin_organizers_pending_stats'),
    path('api/admin/organizers/pending/', admin_api.organizers_pending_api, name='admin_organizers_pending'),
    path('api/admin/organizers/create/', admin_api.organizer_create_api, name='admin_organizers_create'),
    path('api/admin/organizers/<int:organizer_id>/', admin_api.organizer_detail_api, name='admin_organizer_detail'),
    path('api/admin/organizers/<int:organizer_id>/verify/', admin_api.organizer_verify_api, name='admin_organizer_verify'),
    path('api/admin/organizers/<int:organizer_id>/approve/', admin_api.organizer_verify_api, name='admin_organizer_approve'),
    path('api/admin/organizers/<int:organizer_id>/reject/', admin_api.organizer_reject_api, name='admin_organizer_reject'),
    path('api/admin/organizers/<int:organizer_id>/suspend/', admin_api.organizer_suspend_api, name='admin_organizer_suspend'),
    path('api/admin/organizers/<int:organizer_id>/reactivate/', admin_api.organizer_reactivate_api, name='admin_organizer_reactivate'),
    path('api/admin/organizers/<int:organizer_id>/delete/', admin_api.organizer_delete_api, name='admin_organizer_delete'),

    # Tickets Management
    path('api/admin/tickets/', admin_api.tickets_list_api, name='admin_tickets_list'),
    path('api/admin/tickets/export/', admin_api.tickets_export, name='admin_tickets_export'),
    path('api/admin/tickets/<str:ticket_number>/', admin_api.ticket_detail_api, name='admin_ticket_detail'),
    path('api/admin/tickets/<str:ticket_number>/checkin/', admin_api.ticket_checkin_api, name='admin_ticket_checkin'),
    path('api/admin/tickets/<str:ticket_number>/verify/', admin_api.ticket_verify_api, name='admin_ticket_verify'),
    path('api/admin/tickets/<str:ticket_number>/download/', admin_api.ticket_download_api, name='admin_ticket_download'),
    path('api/admin/events/<int:event_id>/stats/', admin_api.event_tickets_stats, name='admin_event_tickets_stats'),
    path('api/admin/events/<int:event_id>/recent-checkins/', admin_api.event_recent_checkins, name='admin_event_recent_checkins'),

    # Check-in History & Analytics Endpoints
    path('api/admin/checkins/stats/', admin_api.checkin_stats, name='admin_checkin_stats'),
    path('api/admin/checkins/events/', admin_api.checkin_events, name='admin_checkin_events'),
    path('api/admin/checkins/recent/', admin_api.checkin_recent, name='admin_checkin_recent'),
    path('api/admin/checkins/event/<int:event_id>/details/', admin_api.checkin_event_details, name='admin_checkin_event_details'),
    path('api/admin/checkins/event/<int:event_id>/timeline/', admin_api.checkin_event_timeline, name='admin_checkin_event_timeline'),
    path('api/admin/checkins/export/', admin_api.checkin_export, name='admin_checkin_export'),
    path('api/admin/checkins/event/<int:event_id>/export/', admin_api.checkin_event_export, name='admin_checkin_event_export'),


    # Payments & Payouts Management
    path('api/admin/transactions/', admin_api.transactions_list_api, name='admin_transactions_list'),
    path('api/admin/transactions/stats/', admin_api.transactions_stats, name='admin_transactions_stats'),
    path('api/admin/transactions/export/', admin_api.transactions_export, name='admin_transactions_export'),
    path('api/admin/transactions/<str:transaction_id>/', admin_api.transaction_detail_api, name='admin_transaction_detail'),
    path('api/admin/transactions/refund/', admin_api.transaction_refund_api, name='admin_transaction_refund'),
    path('api/admin/payouts/', admin_api.payouts_list_api, name='admin_payouts_list'),
    path('api/admin/payouts/stats/', admin_api.payouts_stats, name='admin_payouts_stats'),
    path('api/admin/payouts/process/', admin_api.payout_process, name='admin_payout_process'),
    path('api/admin/payouts/process-all/', admin_api.payout_process_all, name='admin_payout_process_all'),
    path('api/admin/payouts/<int:payout_id>/', admin_api.payout_detail_api, name='admin_payout_detail'),

    # Reports & Analytics
    path('api/admin/reports/kpi/', admin_api.reports_kpi, name='admin_reports_kpi'),
    path('api/admin/reports/revenue-chart/', admin_api.revenue_chart, name='admin_reports_revenue_chart'),
    path('api/admin/reports/category-chart/', admin_api.categories_chart, name='admin_reports_category_chart'),
    path('api/admin/reports/top-events/', admin_api.top_events, name='admin_reports_top_events'),
    path('api/admin/reports/user-growth/', admin_api.user_growth_chart, name='admin_reports_user_growth'),
    path('api/admin/reports/summary/', admin_api.reports_kpi, name='admin_reports_summary'),
    path('api/admin/reports/sales/', admin_api.reports_sales, name='admin_reports_sales'),
    path('api/admin/reports/events/', admin_api.reports_events_api, name='admin_reports_events'),
    path('api/admin/reports/events/summary/', admin_api.reports_events_summary, name='admin_reports_events_summary'),

    # Support Tickets
    path('api/admin/support/tickets/', admin_api.support_tickets_list, name='admin_support_tickets_list'),
    path('api/admin/support/stats/', admin_api.support_stats, name='admin_support_stats'),
    path('api/admin/support/tickets/<int:ticket_id>/', admin_api.support_ticket_detail_api, name='admin_support_ticket_detail'),
    path('api/admin/support/tickets/<int:ticket_id>/reply/', admin_api.support_ticket_reply, name='admin_support_ticket_reply'),

    # Notifications
    path('api/admin/notifications/', admin_api.notifications_api, name='admin_notifications'),
    path('api/admin/notifications/recent/', admin_api.api_notifications_recent, name='admin_notifications_recent'),
    path('api/admin/notifications/mark-all-read/', admin_api.api_notifications_mark_all_read, name='admin_notifications_mark_all_read'),
    path('api/admin/notifications/prune/', admin_api.api_notifications_prune, name='admin_notifications_prune'),
    path('api/admin/notifications/<str:notification_id>/read/', admin_api.api_notification_mark_read, name='admin_notification_mark_read'),
    path('api/admin/notifications/<str:notification_id>/dismiss/', admin_api.api_notification_dismiss, name='admin_notification_dismiss'),
    path('api/admin/notifications/<str:notification_id>/', admin_api.api_notification_delete, name='admin_notification_delete'),

    # Settings & Profile
    path('api/admin/user/profile/', admin_api.user_profile, name='admin_user_profile'),
    path('api/admin/profile/', admin_api.user_profile, name='admin_profile'),
    path('api/admin/profile/update/', admin_api.user_profile_update, name='admin_profile_update'),
    path('api/admin/profile/change-password/', admin_api.user_profile_change_password, name='admin_profile_change_password'),
    path('api/admin/profile/stats/', admin_api.user_profile_stats, name='admin_profile_stats'),
    path('api/admin/settings/', admin_api.settings_api, name='admin_settings_api'),
    path('api/admin/settings/general/', admin_api.settings_general_api, name='admin_settings_general'),
    path('api/admin/broadcast/', admin_api.api_admin_broadcast, name='admin_settings_broadcast'),

    # Payments - M-Pesa
    path('payments/', include('payments.urls')),
    
    # DB Status Diagnostics
    path('api/events/db-status/', api_db_status, name='api_db_status'),
    path('api/events/run-migrations/', api_run_migrations, name='api_run_migrations'),
    
    # Portal URLs
    path('', include('config.attendee_urls')),
    path('attendee/', include('config.attendee_urls')),
    path('organizer/', include('config.organizer_urls')),
    path('admin-portal/', include('config.admin_urls')),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
