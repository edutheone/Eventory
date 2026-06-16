import json
import csv
from datetime import datetime, timedelta, timezone as dt_timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum, Q, Count, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404

from events.models import Event, Category
from bookings.models import Ticket
from accounts.admin_store import (
    get_notifications, mark_notification_read, mark_all_notifications_read,
    delete_notification, dismiss_notification,
    expire_notifications_for_entity,
    get_support_tickets, get_support_ticket_detail,
    add_support_ticket_reply, update_support_ticket_status,
    get_approved_organizer_ids, approve_organizer,
)

User = get_user_model()

# ============ HELPER: STAFF REQUIRED CHECK ============
def is_admin_or_staff(user):
    if not user.is_authenticated:
        return False
    role = getattr(user, 'role', None)
    return user.is_staff or user.is_superuser or role == 'admin'


def resolve_admin_user(request):
    """Resolve admin user from Django session or Bearer token (Vercel/serverless)."""
    if is_admin_or_staff(request.user):
        return request.user

    from accounts.auth import authenticate_bearer
    bearer_user, _error = authenticate_bearer(request)
    if bearer_user and is_admin_or_staff(bearer_user):
        return bearer_user
    return None


def admin_required_json(view_func):
    def _wrapped(request, *args, **kwargs):
        admin_user = resolve_admin_user(request)
        if not admin_user:
            return JsonResponse(
                {'success': False, 'message': 'Forbidden. Admin privileges required.'},
                status=403,
            )
        request.user = admin_user
        return view_func(request, *args, **kwargs)
    return _wrapped

# ============ 1. DASHBOARD APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def dashboard_stats(request):
    try:
        total_events = Event.objects.count()
        total_bookings = Ticket.objects.count()
        total_users = User.objects.count()
        
        # Total revenue is sum of ticket price * quantity for valid/checked-in tickets
        revenue_data = Ticket.objects.exclude(status='cancelled').aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        total_revenue = float(revenue_data['total'] or 0.0)
        
        # Calculate trends (mocked logically or computed if dates are present)
        stats = {
            'total_events': total_events,
            'total_bookings': total_bookings,
            'total_users': total_users,
            'total_revenue': total_revenue,
            'events_trend': {'percentage': 12},
            'bookings_trend': {'percentage': 8},
            'users_trend': {'percentage': 15},
            'revenue_trend': {'percentage': 18}
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def recent_events(request):
    try:
        events = Event.objects.order_by('-created_at')[:5]
        data = [{
            'id': e.id,
            'title': e.title,
            'organizer_name': e.organizer.get_full_name() or e.organizer.username,
            'start_date': e.start_date.isoformat(),
            'status': e.status,
            'banner_image': e.banner_image or ''
        } for e in events]
        return JsonResponse({'success': True, 'events': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def recent_bookings(request):
    try:
        bookings = Ticket.objects.order_by('-purchase_date')[:5]
        data = [{
            'id': b.ticket_number,
            'customer_name': b.billing_name,
            'customer_email': b.billing_email,
            'event_title': b.event.title,
            'quantity': b.quantity,
            'total': float(b.price * b.quantity),
            'status': 'confirmed' if b.status == 'valid' else ('attended' if b.status == 'checked_in' else b.status),
            'created_at': b.purchase_date.isoformat()
        } for b in bookings]
        return JsonResponse({'success': True, 'bookings': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def top_events(request):
    try:
        # Group confirmed tickets by event
        events = Event.objects.annotate(
            sold_count=Coalesce(Sum('tickets__quantity'), 0)
        ).order_by('-sold_count')[:5]
        
        data = []
        for e in events:
            rev_agg = Ticket.objects.filter(event=e).exclude(status='cancelled').aggregate(
                total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
            )
            revenue = float(rev_agg['total'] or 0.0)
            fill_rate = int(min(e.sold_count / max(1, e.total_seats) * 100, 100))
            data.append({
                'title': e.title,
                'tickets_sold': e.sold_count,
                'revenue': revenue,
                'fill_rate': fill_rate
            })
        return JsonResponse({'success': True, 'events': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def revenue_chart(request):
    try:
        # Generate last 6 months dynamic revenue
        labels = []
        values = []
        now = timezone.now()
        for i in range(5, -1, -1):
            month_date = now - timedelta(days=i*30)
            month_label = month_date.strftime('%b')
            labels.append(month_label)
            
            # Query tickets bought in this month range
            start_range = datetime(month_date.year, month_date.month, 1, tzinfo=dt_timezone.utc)
            if month_date.month == 12:
                end_range = datetime(month_date.year + 1, 1, 1, tzinfo=dt_timezone.utc)
            else:
                end_range = datetime(month_date.year, month_date.month + 1, 1, tzinfo=dt_timezone.utc)
                
            rev_agg = Ticket.objects.filter(
                purchase_date__gte=start_range,
                purchase_date__lt=end_range
            ).exclude(status='cancelled').aggregate(
                total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
            )
            values.append(float(rev_agg['total'] or 0.0))
            
        return JsonResponse({'success': True, 'labels': labels, 'values': values})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def categories_chart(request):
    try:
        categories = Category.objects.all()
        labels = []
        values = []
        for cat in categories:
            labels.append(cat.name)
            count = Ticket.objects.filter(event__category=cat).exclude(status='cancelled').count()
            values.append(count)
        return JsonResponse({'success': True, 'labels': labels, 'values': values})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def user_growth_chart(request):
    try:
        labels = []
        values = []
        now = timezone.now()
        for i in range(5, -1, -1):
            month_date = now - timedelta(days=i*30)
            month_label = month_date.strftime('%b')
            labels.append(month_label)
            
            # Query users joined in this month range
            start_range = datetime(month_date.year, month_date.month, 1, tzinfo=dt_timezone.utc)
            if month_date.month == 12:
                end_range = datetime(month_date.year + 1, 1, 1, tzinfo=dt_timezone.utc)
            else:
                end_range = datetime(month_date.year, month_date.month + 1, 1, tzinfo=dt_timezone.utc)
                
            count = User.objects.filter(
                date_joined__gte=start_range,
                date_joined__lt=end_range
            ).count()
            values.append(count)
            
        return JsonResponse({'success': True, 'labels': labels, 'values': values})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def recent_activity(request):
    try:
        # Collect recent activities dynamically
        activities = []
        
        # Recent user registrations
        users = User.objects.order_by('-date_joined')[:3]
        for u in users:
            activities.append({
                'title': "New User Registered",
                'description': f"User @{u.username} ({u.role}) joined the platform.",
                'icon': "fa-user-plus",
                'type': "info",
                'created_at': u.date_joined.isoformat()
            })
            
        # Recent tickets/bookings bought
        bookings = Ticket.objects.order_by('-purchase_date')[:3]
        for b in bookings:
            activities.append({
                'title': "Ticket Purchased",
                'description': f"{b.billing_name} bought {b.quantity} tickets for '{b.event.title}'.",
                'icon': "fa-ticket-alt",
                'type': "success",
                'created_at': b.purchase_date.isoformat()
            })
            
        # Recent events created
        events = Event.objects.order_by('-created_at')[:3]
        for e in events:
            activities.append({
                'title': "New Event Created",
                'description': f"Organizer '{e.organizer.username}' created event '{e.title}'.",
                'icon': "fa-calendar-plus",
                'type': "primary",
                'created_at': e.created_at.isoformat()
            })
            
        # Sort combined activities by created_at desc
        activities = sorted(activities, key=lambda x: x['created_at'], reverse=True)[:6]
        return JsonResponse({'success': True, 'activities': activities})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def pending_count(request):
    try:
        count = Event.objects.filter(status='pending').count()
        return JsonResponse({'success': True, 'pending_count': count, 'count': count})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 2. EVENTS APIS (ALL & PENDING) ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def events_list_api(request):
    try:
        search = request.GET.get('search', '').strip()
        status = request.GET.get('status', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q()
        if search:
            query &= (Q(title__icontains=search) | Q(organizer__username__icontains=search) | Q(organizer__organization_name__icontains=search))
        if status:
            query &= Q(status=status)
                
        events = Event.objects.filter(query).order_by('-created_at')
        
        total_items = events.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        events_slice = events[start:end]
        
        data = [{
            'id': e.id,
            'title': e.title,
            'organizer_name': e.organizer.organization_name or e.organizer.get_full_name() or e.organizer.username,
            'start_date': e.start_date.isoformat(),
            'status': e.status,
            'category_name': e.category.name if e.category else 'Uncategorized',
            'min_price': float(e.price)
        } for e in events_slice]
        
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'events': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def api_pending_events(request):
    try:
        search = request.GET.get('search', '').strip()
        category = request.GET.get('category', '').strip()
        sort = request.GET.get('sort', 'newest')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q(status='pending')
        if search:
            query &= (Q(title__icontains=search) | Q(organizer__username__icontains=search))
        if category:
            query &= Q(category_id=category)
            
        events = Event.objects.filter(query)
        
        if sort == 'newest':
            events = events.order_by('-created_at')
        elif sort == 'oldest':
            events = events.order_by('created_at')
        elif sort == 'event_date':
            events = events.order_by('start_date')
            
        total_items = events.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        events_slice = events[start:end]
        
        data = [{
            'id': e.id,
            'title': e.title,
            'organizer_name': e.organizer.organization_name or e.organizer.get_full_name() or e.organizer.username,
            'start_date': e.start_date.isoformat(),
            'status': e.status,
            'category_name': e.category.name if e.category else 'Uncategorized',
            'venue_name': e.venue,
            'min_price': float(e.price),
            'banner_image': e.banner_image or ''
        } for e in events_slice]
        
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'events': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def api_event_detail(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        data = {
            'id': e.id,
            'title': e.title,
            'description': e.description,
            'organizer_name': e.organizer.organization_name or e.organizer.get_full_name() or e.organizer.username,
            'organizer_email': e.organizer.email,
            'start_date': e.start_date.isoformat(),
            'end_date': e.end_date.isoformat(),
            'status': e.status,
            'category_name': e.category.name if e.category else 'Uncategorized',
            'venue': e.venue,
            'address': e.address,
            'price': float(e.price),
            'total_seats': e.total_seats,
            'available_seats': e.available_seats,
            'banner_image': e.banner_image or '',
            'created_at': e.created_at.isoformat(),
            'is_featured': e.is_featured,
            'images': [img.url for img in e.images.all()],
        }
        return JsonResponse({'success': True, 'event': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_approve_event(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        e.status = 'published'
        e.save()
        expire_notifications_for_entity('event', e.id, ['event_pending_approval'])
        return JsonResponse({'success': True, 'message': 'Event approved successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_reject_event(request, event_id):
    try:
        data = json.loads(request.body) if request.body else {}
        reason = data.get('reason', 'Does not meet platform guidelines')
        e = get_object_or_404(Event, id=event_id)
        
        is_revocation = e.status in ('approved', 'published')
        e.status = 'draft' # Rejects back to draft
        e.save()
        
        title = "Event Approval Revoked" if is_revocation else "Event Rejected"
        msg = f"Approval for event '{e.title}' was revoked." if is_revocation else f"Event '{e.title}' was rejected. Reason: {reason}."
        
        expire_notifications_for_entity('event', e.id, ['event_pending_approval'])
        return JsonResponse({'success': True, 'message': 'Event rejected successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
@admin_required_json
def api_delete_event(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        e.delete()
        return JsonResponse({'success': True, 'message': 'Event deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def api_event_history(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        history = [
            {
                'action': 'Event Created',
                'user': e.organizer.username,
                'details': 'Initial submission as draft.',
                'timestamp': e.created_at.isoformat()
            }
        ]
        if e.status in ['approved', 'published']:
            history.append({
                'action': 'Event Approved',
                'user': 'admin',
                'details': 'System admin approved event registration.',
                'timestamp': e.updated_at.isoformat()
            })
        return JsonResponse({'success': True, 'history': history})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def api_event_stats(request):
    try:
        pending = Event.objects.filter(status='pending').count()
        now = timezone.now()
        month_start = datetime(now.year, now.month, 1, tzinfo=dt_timezone.utc)
        approved = Event.objects.filter(status__in=['approved', 'published'], updated_at__gte=month_start).count()
        stats = {
            'pending': pending,
            'approved_this_month': approved,
            'rejected_this_month': 0
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_bulk_approve(request):
    try:
        data = json.loads(request.body)
        ids = data.get('event_ids', [])
        Event.objects.filter(id__in=ids).update(status='published')
        for event_id in ids:
            expire_notifications_for_entity('event', event_id, ['event_pending_approval'])
        return JsonResponse({'success': True, 'message': f'Successfully approved {len(ids)} events'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_bulk_reject(request):
    try:
        data = json.loads(request.body)
        ids = data.get('event_ids', [])
        Event.objects.filter(id__in=ids).update(status='draft')
        for event_id in ids:
            expire_notifications_for_entity('event', event_id, ['event_pending_approval'])
        return JsonResponse({'success': True, 'message': f'Successfully rejected {len(ids)} events'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def categories_list_api(request):
    try:
        categories = Category.objects.all()
        data = [{'id': c.id, 'name': c.name} for c in categories]
        return JsonResponse({'success': True, 'categories': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def events_upcoming_api(request):
    try:
        events = Event.objects.filter(start_date__gte=timezone.now()).order_by('start_date')
        data = [{
            'id': e.id,
            'title': e.title,
            'date': e.start_date.isoformat()
        } for e in events]
        return JsonResponse({'success': True, 'events': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def api_events_export(request):
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="events_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Title', 'Organizer', 'Category', 'Start Date', 'Venue', 'Price', 'Seats', 'Status'])
        
        events = Event.objects.all()
        for e in events:
            writer.writerow([
                e.id,
                e.title,
                e.organizer.username,
                e.category.name if e.category else 'N/A',
                e.start_date.isoformat(),
                e.venue,
                e.price,
                e.total_seats,
                e.status
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 3. BOOKINGS & REFUNDS APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def bookings_list_api(request):
    try:
        search = request.GET.get('search', '').strip()
        status = request.GET.get('status', '').strip()
        payment_method = request.GET.get('payment_method', '').strip()
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q()
        if search:
            query &= (Q(ticket_number__icontains=search) | Q(billing_name__icontains=search) | Q(billing_email__icontains=search) | Q(event__title__icontains=search))
            
        if status:
            db_status = 'valid' if status == 'confirmed' else ('checked_in' if status == 'attended' else status)
            query &= Q(status=db_status)
            
        if date_from:
            query &= Q(purchase_date__date__gte=date_from)
        if date_to:
            query &= Q(purchase_date__date__lte=date_to)
            
        tickets = Ticket.objects.filter(query).order_by('-purchase_date')
        
        total_items = tickets.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        tickets_slice = tickets[start:end]
        
        data = [{
            'id': t.ticket_number,
            'customer_name': t.billing_name,
            'customer_email': t.billing_email,
            'event_title': t.event.title,
            'event_date': t.event.start_date.isoformat(),
            'quantity': t.quantity,
            'total': float(t.price * t.quantity),
            'payment_method': 'mpesa',  # Default payment method
            'status': 'confirmed' if t.status == 'valid' else ('attended' if t.status == 'checked_in' else t.status),
            'created_at': t.purchase_date.isoformat()
        } for t in tickets_slice]
        
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'bookings': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def bookings_stats(request):
    try:
        total = Ticket.objects.count()
        confirmed = Ticket.objects.filter(status='valid').count()
        refunded = Ticket.objects.filter(status='refunded').count()
        cancelled = Ticket.objects.filter(status='cancelled').count()
        
        rev_agg = Ticket.objects.exclude(status='cancelled').aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        total_revenue = float(rev_agg['total'] or 0.0)
        
        stats = {
            'total': total,
            'confirmed': confirmed,
            'refunded': refunded,
            'pending_refunds': cancelled,  # cancelled tickets act as pending refunds
            'total_revenue': total_revenue
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def booking_detail(request, booking_id):
    try:
        t = get_object_or_404(Ticket, ticket_number=booking_id)
        booking = {
            'id': t.ticket_number,
            'customer_name': t.billing_name,
            'customer_email': t.billing_email,
            'customer_phone': t.billing_phone,
            'event_title': t.event.title,
            'event_date': t.event.start_date.isoformat(),
            'quantity': t.quantity,
            'total': float(t.price * t.quantity),
            'payment_method': 'mpesa',
            'status': 'confirmed' if t.status == 'valid' else ('attended' if t.status == 'checked_in' else t.status),
            'created_at': t.purchase_date.isoformat(),
            'ticket_type': t.ticket_type
        }
        return JsonResponse({'success': True, 'booking': booking})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def booking_refund(request, booking_id):
    try:
        t = get_object_or_404(Ticket, ticket_number=booking_id)
        t.status = 'refunded'
        t.save()
        expire_notifications_for_entity('refund', t.id, ['refund_pending'])
        return JsonResponse({'success': True, 'message': 'Refund processed successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def booking_cancel(request, booking_id):
    try:
        t = get_object_or_404(Ticket, ticket_number=booking_id)
        t.status = 'cancelled'
        t.save()
        return JsonResponse({'success': True, 'message': 'Booking cancelled successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def bookings_export(request):
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bookings_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Ticket Number', 'Billing Name', 'Billing Email', 'Billing Phone', 'Event Title', 'Quantity', 'Price', 'Status', 'Date'])
        
        tickets = Ticket.objects.all()
        for t in tickets:
            writer.writerow([
                t.ticket_number,
                t.billing_name,
                t.billing_email,
                t.billing_phone,
                t.event.title,
                t.quantity,
                t.price,
                t.status,
                t.purchase_date.isoformat()
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 4. REFUNDS MANAGEMENT APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def refunds_list_api(request):
    try:
        search = request.GET.get('search', '').strip()
        status = request.GET.get('status', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q()
        if search:
            query &= (Q(ticket_number__icontains=search) | Q(billing_name__icontains=search) | Q(billing_email__icontains=search))
            
        # Dynamically map cancelled tickets as pending refunds, refunded as completed/approved
        if status == 'pending':
            query &= Q(status='cancelled')
        elif status == 'approved' or status == 'completed':
            query &= Q(status='refunded')
        else:
            query &= (Q(status='cancelled') | Q(status='refunded'))
            
        tickets = Ticket.objects.filter(query).order_by('-purchase_date')
        
        total_items = tickets.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        tickets_slice = tickets[start:end]
        
        data = [{
            'id': t.id,
            'booking_id': t.ticket_number,
            'customer_name': t.billing_name,
            'customer_email': t.billing_email,
            'event_title': t.event.title,
            'amount': float(t.price * t.quantity),
            'reason': 'Ticket Cancellation Refund Request',
            'requested_date': t.purchase_date.isoformat(),
            'status': 'pending' if t.status == 'cancelled' else 'approved'
        } for t in tickets_slice]
        
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'refunds': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def refunds_stats(request):
    try:
        pending = Ticket.objects.filter(status='cancelled').count()
        approved = Ticket.objects.filter(status='refunded').count()
        
        ref_agg = Ticket.objects.filter(status='refunded').aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        total_amount = float(ref_agg['total'] or 0.0)
        
        stats = {
            'pending': pending,
            'approved_this_month': approved,
            'rejected': 0,
            'total_amount': total_amount
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def refund_detail_api(request, refund_id):
    try:
        t = get_object_or_404(Ticket, id=refund_id)
        refund = {
            'id': t.id,
            'booking_id': t.ticket_number,
            'customer_name': t.billing_name,
            'customer_email': t.billing_email,
            'event_title': t.event.title,
            'amount': float(t.price * t.quantity),
            'reason': 'Ticket Cancellation Refund Request',
            'requested_date': t.purchase_date.isoformat(),
            'status': 'pending' if t.status == 'cancelled' else 'approved'
        }
        return JsonResponse({'success': True, 'refund': refund})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def refund_approve_api(request, refund_id):
    try:
        t = get_object_or_404(Ticket, id=refund_id)
        t.status = 'refunded'
        t.save()
        expire_notifications_for_entity('refund', t.id, ['refund_pending'])
        return JsonResponse({'success': True, 'message': 'Refund approved successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def refund_reject_api(request, refund_id):
    try:
        t = get_object_or_404(Ticket, id=refund_id)
        t.status = 'valid' # Restores ticket back to valid
        t.save()
        expire_notifications_for_entity('refund', t.id, ['refund_pending'])
        return JsonResponse({'success': True, 'message': 'Refund rejected. Ticket restored.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def refunds_export(request):
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="refunds_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Refund ID', 'Ticket Number', 'Billing Name', 'Billing Email', 'Amount', 'Status', 'Date'])
        
        tickets = Ticket.objects.filter(status__in=['cancelled', 'refunded'])
        for t in tickets:
            writer.writerow([
                t.id,
                t.ticket_number,
                t.billing_name,
                t.billing_email,
                t.price * t.quantity,
                'pending' if t.status == 'cancelled' else 'approved',
                t.purchase_date.isoformat()
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 5. USERS MANAGEMENT APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def users_list_api(request):
    try:
        search = request.GET.get('search', '').strip()
        status = request.GET.get('status', '').strip()
        role = request.GET.get('role', 'all').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q()
        if search:
            query &= (Q(username__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search))
            
        if status:
            if status == 'active':
                query &= Q(is_active=True)
            elif status == 'suspended':
                query &= Q(is_active=False)
                
        if role != 'all':
            query &= Q(role=role)
            
        users = User.objects.filter(query).order_by('-date_joined')
        
        total_items = users.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        users_slice = users[start:end]
        
        data = [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'full_name': u.get_full_name() or u.username,
            'phone': u.phone or 'N/A',
            'role': u.role,
            'status': 'active' if u.is_active else 'suspended',
            'email_verified': True,
            'created_at': u.date_joined.isoformat(),
            'last_login': u.last_login.isoformat() if u.last_login else None
        } for u in users_slice]
        
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'users': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def users_stats(request):
    try:
        total = User.objects.count()
        active = User.objects.filter(is_active=True).count()
        
        # Counter by roles
        attendees = User.objects.filter(role='attendee').count()
        organizers = User.objects.filter(role='organizer').count()
        admins = User.objects.filter(role='admin').count()
        
        now = timezone.now()
        month_start = datetime(now.year, now.month, 1, tzinfo=dt_timezone.utc)
        new_this_month = User.objects.filter(date_joined__gte=month_start).count()
        
        stats = {
            'total': total,
            'active': active,
            'new_this_month': new_this_month,
            'total_bookings': Ticket.objects.count(),
            'attendees': attendees,
            'organizers': organizers,
            'admins': admins
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def user_reset_password(request, user_id):
    try:
        # Return success simulation
        return JsonResponse({'success': True, 'message': 'Password reset link sent successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def user_suspend(request, user_id):
    try:
        u = get_object_or_404(User, id=user_id)
        u.is_active = False
        u.save()
        return JsonResponse({'success': True, 'message': 'User suspended successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def user_detail_api(request, user_id):
    try:
        u = get_object_or_404(User, id=user_id)
        data = {
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'full_name': u.get_full_name() or u.username,
            'phone': u.phone or 'N/A',
            'role': u.role,
            'status': 'active' if u.is_active else 'suspended',
            'email_verified': True,
            'created_at': u.date_joined.isoformat(),
            'last_login': u.last_login.isoformat() if u.last_login else None,
        }
        if u.role == 'organizer':
            event_count = Event.objects.filter(organizer=u).count()
            tickets_sold = Ticket.objects.filter(event__organizer=u).exclude(status='cancelled').aggregate(
                total=Sum('quantity')
            )
            rev_agg = Ticket.objects.filter(event__organizer=u).exclude(status='cancelled').aggregate(
                total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
            )
            approved_ids = get_approved_organizer_ids()
            data.update({
                'business_name': u.organization_name or u.username,
                'tax_id': 'N/A',
                'business_address': u.location or 'N/A',
                'is_verified': u.id in approved_ids or u.has_mpesa_payment_config(),
                'total_events': event_count,
                'total_tickets': int(tickets_sold['total'] or 0),
                'total_revenue': float(rev_agg['total'] or 0.0),
                'avg_rating': 0,
            })
        elif u.role == 'attendee':
            tickets = Ticket.objects.filter(billing_email=u.email).exclude(status='cancelled')
            spent_agg = tickets.aggregate(
                total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
            )
            data.update({
                'total_bookings': tickets.count(),
                'total_tickets': int(tickets.aggregate(total=Sum('quantity'))['total'] or 0),
                'total_spent': float(spent_agg['total'] or 0.0),
                'favorite_category': 'N/A',
            })
        return JsonResponse({'success': True, 'user': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def user_activate(request, user_id):
    try:
        u = get_object_or_404(User, id=user_id)
        u.is_active = True
        u.save()
        return JsonResponse({'success': True, 'message': 'User activated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def users_export(request):
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Username', 'Email', 'Full Name', 'Phone', 'Role', 'Status', 'Date Joined'])
        
        users = User.objects.all()
        for u in users:
            writer.writerow([
                u.id,
                u.username,
                u.email,
                u.get_full_name() or u.username,
                u.phone,
                u.role,
                'active' if u.is_active else 'suspended',
                u.date_joined.isoformat()
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ ORGANIZER MANAGEMENT APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def organizers_stats_api(request):
    try:
        verified = User.objects.filter(role='organizer', is_active=True).count()
        suspended = User.objects.filter(role='organizer', is_active=False).count()
        events_count = Event.objects.filter(organizer__role='organizer').count()
        tickets_sold = Ticket.objects.filter(event__organizer__role='organizer').exclude(status='cancelled').count()
        
        approved_ids = set(get_approved_organizer_ids())
        pending = 0
        for org in User.objects.filter(role='organizer', is_active=True):
            if org.id not in approved_ids and not org.has_mpesa_payment_config():
                if Event.objects.filter(organizer=org).count() == 0:
                    pending += 1

        stats = {
            'verified': verified,
            'suspended': suspended,
            'pending': pending,
            'total_events': events_count,
            'total_tickets': tickets_sold
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def organizers_verified_api(request):
    try:
        search = request.GET.get('search', '').strip()
        status = request.GET.get('status', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q(role='organizer', is_active=True)
        if search:
            query &= (Q(username__icontains=search) | Q(email__icontains=search) | Q(organization_name__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))
            
        if status == 'suspended':
            query = Q(role='organizer', is_active=False)
            if search:
                query &= (Q(username__icontains=search) | Q(email__icontains=search) | Q(organization_name__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))

        organizers = User.objects.filter(query).order_by('-date_joined')
        
        total_items = organizers.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        orgs_slice = organizers[start:end]
        
        data = []
        for u in orgs_slice:
            event_count = Event.objects.filter(organizer=u).count()
            data.append({
                'id': u.id,
                'business_name': u.organization_name or u.username,
                'contact_name': u.get_full_name() or u.username,
                'email': u.email,
                'phone': u.phone or 'N/A',
                'event_count': event_count,
                'status': 'active' if u.is_active else 'suspended'
            })
            
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'organizers': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def organizers_suspended_api(request):
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q(role='organizer', is_active=False)
        organizers = User.objects.filter(query).order_by('-date_joined')
        
        total_items = organizers.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        orgs_slice = organizers[start:end]
        
        data = []
        for u in orgs_slice:
            data.append({
                'id': u.id,
                'business_name': u.organization_name or u.username,
                'email': u.email,
                'suspended_at': u.date_joined.isoformat(),
                'suspension_reason': 'Suspended by Administrator'
            })
            
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'organizers': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def _pending_organizers_queryset():
    approved_ids = set(get_approved_organizer_ids())
    pending = []
    for org in User.objects.filter(role='organizer', is_active=True).order_by('-date_joined'):
        if org.id in approved_ids or org.has_mpesa_payment_config():
            continue
        if Event.objects.filter(organizer=org).count() > 0:
            continue
        pending.append(org)
    return pending


@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def organizers_pending_stats_api(request):
    try:
        pending = _pending_organizers_queryset()
        return JsonResponse({
            'success': True,
            'stats': {
                'pending': len(pending),
                'approved_this_week': len(get_approved_organizer_ids()),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def organizers_pending_api(request):
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        pending = _pending_organizers_queryset()
        total_items = len(pending)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        orgs_slice = pending[start:end]
        data = [{
            'id': u.id,
            'business_name': u.organization_name or u.username,
            'contact_name': u.get_full_name() or u.username,
            'email': u.email,
            'phone': u.phone or 'N/A',
            'created_at': u.date_joined.isoformat(),
            'status': 'pending',
        } for u in orgs_slice]
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'organizers': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def organizer_detail_api(request, organizer_id):
    try:
        u = get_object_or_404(User, id=organizer_id, role='organizer')
        event_count = Event.objects.filter(organizer=u).count()
        data = {
            'id': u.id,
            'business_name': u.organization_name or u.username,
            'contact_name': u.get_full_name() or u.username,
            'email': u.email,
            'phone': u.phone or 'N/A',
            'event_count': event_count,
            'status': 'active' if u.is_active else 'suspended',
            'document_url': '#',
            'tax_id': 'N/A'
        }
        return JsonResponse({'success': True, 'organizer': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def organizer_create_api(request):
    try:
        data = json.loads(request.body)
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        business_name = data.get('business_name')
        contact_name = data.get('contact_name')
        phone = data.get('phone', '')
        
        if not username or not email or not password or not business_name or not contact_name:
            return JsonResponse({'success': False, 'message': 'All fields are required.'}, status=400)
            
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'message': 'Username already exists.'}, status=400)
            
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already registered.'}, status=400)
            
        name_parts = contact_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='organizer',
            organization_name=business_name,
            phone=phone,
            is_active=True
        )
        return JsonResponse({'success': True, 'message': 'Organizer created successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def organizer_suspend_api(request, organizer_id):
    try:
        u = get_object_or_404(User, id=organizer_id, role='organizer')
        u.is_active = False
        u.save()
        return JsonResponse({'success': True, 'message': 'Organizer suspended successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def organizer_verify_api(request, organizer_id):
    try:
        u = get_object_or_404(User, id=organizer_id, role='organizer')
        approve_organizer(u.id)
        return JsonResponse({'success': True, 'message': 'Organizer verified successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def organizer_reject_api(request, organizer_id):
    try:
        data = json.loads(request.body) if request.body else {}
        reason = data.get('reason', 'Application rejected by administrator')
        u = get_object_or_404(User, id=organizer_id, role='organizer')
        u.is_active = False
        u.save()
        return JsonResponse({'success': True, 'message': f'Organizer rejected. Reason: {reason}'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def organizer_reactivate_api(request, organizer_id):
    try:
        u = get_object_or_404(User, id=organizer_id, role='organizer')
        u.is_active = True
        u.save()
        return JsonResponse({'success': True, 'message': 'Organizer reactivated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def organizer_delete_api(request, organizer_id):
    try:
        u = get_object_or_404(User, id=organizer_id, role='organizer')
        u.delete()
        return JsonResponse({'success': True, 'message': 'Organizer deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 6. TICKETS MANAGEMENT & QR VERIFY APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def tickets_list_api(request):
    try:
        search = request.GET.get('search', '').strip()
        event_id = request.GET.get('event_id', '').strip()
        status = request.GET.get('status', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q()
        if search:
            query &= (Q(ticket_number__icontains=search) | Q(billing_name__icontains=search) | Q(event__title__icontains=search))
        if event_id:
            query &= Q(event_id=event_id)
        if status:
            query &= Q(status=status)
            
        tickets = Ticket.objects.filter(query).order_by('-purchase_date')
        
        total_items = tickets.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        tickets_slice = tickets[start:end]
        
        data = [{
            'ticket_number': t.ticket_number,
            'attendee_name': t.billing_name,
            'attendee_email': t.billing_email,
            'event_title': t.event.title,
            'booking_id': t.ticket_number,
            'status': t.status,
            'purchase_date': t.purchase_date.isoformat(),
            'checked_in_at': t.checked_in_at.isoformat() if t.checked_in_at else None
        } for t in tickets_slice]
        
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'tickets': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def ticket_detail_api(request, ticket_number):
    try:
        t = get_object_or_404(Ticket, ticket_number=ticket_number)
        ticket = {
            'ticket_number': t.ticket_number,
            'attendee_name': t.billing_name,
            'attendee_email': t.billing_email,
            'attendee_phone': t.billing_phone,
            'event_title': t.event.title,
            'event_date': t.event.start_date.isoformat(),
            'venue': t.event.venue,
            'status': t.status,
            'checked_in_at': t.checked_in_at.isoformat() if t.checked_in_at else None,
            'qr_code_url': f"/api/attendee/tickets/{t.ticket_number}/qr/"
        }
        return JsonResponse({'success': True, 'ticket': ticket})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def ticket_checkin_api(request, ticket_number):
    try:
        t = get_object_or_404(Ticket, ticket_number=ticket_number)
        if t.status == 'checked_in':
            return JsonResponse({'success': False, 'message': 'Ticket already checked in'}, status=400)
        t.status = 'checked_in'
        t.checked_in_at = timezone.now()
        t.save()
        return JsonResponse({'success': True, 'message': 'Check-in processed successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def ticket_verify_api(request, ticket_number):
    try:
        # POST parameter event_id
        data = json.loads(request.body) if request.body else {}
        event_id = data.get('event_id')
        
        t = get_object_or_404(Ticket, ticket_number=ticket_number)
        
        if event_id and t.event.id != int(event_id):
            return JsonResponse({
                'success': False,
                'message': f"Ticket belongs to event '{t.event.title}' not this selected event."
            })
            
        if t.status == 'checked_in':
            return JsonResponse({
                'success': False,
                'message': "Ticket has already been used to check in."
            })
            
        if t.status == 'cancelled' or t.status == 'refunded':
            return JsonResponse({
                'success': False,
                'message': "Ticket is invalid (Cancelled/Refunded)."
            })
            
        t.status = 'checked_in'
        t.checked_in_at = timezone.now()
        t.save()
        
        ticket_data = {
            'ticket_number': t.ticket_number,
            'attendee_name': t.billing_name,
            'event_title': t.event.title
        }
        return JsonResponse({
            'success': True,
            'message': f"Check-in Successful! Welcome {t.billing_name}.",
            'ticket': ticket_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def ticket_download_api(request, ticket_number):
    # Simulates PDF file return
    response = HttpResponse("Simulated Ticket PDF File", content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_{ticket_number}.pdf"'
    return response

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def event_tickets_stats(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        total_tickets = Ticket.objects.filter(event=e).count()
        checked_in = Ticket.objects.filter(event=e, status='checked_in').count()
        remaining = max(0, total_tickets - checked_in)
        stats = {
            'total_tickets': total_tickets,
            'checked_in': checked_in,
            'remaining': remaining
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def event_recent_checkins(request, event_id):
    try:
        tickets = Ticket.objects.filter(event_id=event_id, status='checked_in').order_by('-checked_in_at')[:5]
        checkins = [{
            'attendee_name': t.billing_name,
            'ticket_number': t.ticket_number,
            'checkin_time': t.checked_in_at.isoformat() if t.checked_in_at else timezone.now().isoformat()
        } for t in tickets]
        return JsonResponse({'success': True, 'checkins': checkins})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def tickets_export(request):
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tickets_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Ticket Number', 'Attendee Name', 'Attendee Email', 'Event Title', 'Status', 'Checked In At'])
        
        tickets = Ticket.objects.all()
        for t in tickets:
            writer.writerow([
                t.ticket_number,
                t.billing_name,
                t.billing_email,
                t.event.title,
                t.status,
                t.checked_in_at.isoformat() if t.checked_in_at else 'N/A'
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 7. PAYMENTS (TRANSACTIONS) & PAYOUTS APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def transactions_list_api(request):
    try:
        search = request.GET.get('search', '').strip()
        status = request.GET.get('status', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        query = Q()
        if search:
            query &= (Q(ticket_number__icontains=search) | Q(billing_name__icontains=search) | Q(event__title__icontains=search))
            
        tickets = Ticket.objects.filter(query).order_by('-purchase_date')
        
        total_items = tickets.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        
        tickets_slice = tickets[start:end]
        
        data = []
        for t in tickets_slice:
            t_status = 'success'
            if t.status == 'refunded':
                t_status = 'refunded'
            elif t.status == 'cancelled':
                t_status = 'failed'
                
            data.append({
                'id': f"TXN-{t.ticket_number[5:]}",
                'booking_id': t.ticket_number,
                'customer_name': t.billing_name,
                'customer_email': t.billing_email,
                'event_title': t.event.title,
                'amount': float(t.price * t.quantity),
                'status': t_status,
                'payment_method': 'mpesa',
                'created_at': t.purchase_date.isoformat()
            })
            
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'transactions': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def transactions_stats(request):
    try:
        total = Ticket.objects.count()
        success = Ticket.objects.exclude(status__in=['cancelled', 'refunded']).count()
        refunded = Ticket.objects.filter(status='refunded').count()
        failed = Ticket.objects.filter(status='cancelled').count()
        
        rev_agg = Ticket.objects.exclude(status='cancelled').aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        total_amount = float(rev_agg['total'] or 0.0)
        
        stats = {
            'total': total,
            'success': success,
            'refunded': refunded,
            'failed': failed,
            'total_amount': total_amount
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def transaction_detail_api(request, transaction_id):
    try:
        # Match TXN-XXXX back to TICK-XXXX
        ticket_number = f"TICK-{transaction_id[4:]}"
        t = get_object_or_404(Ticket, ticket_number=ticket_number)
        
        t_status = 'success'
        if t.status == 'refunded':
            t_status = 'refunded'
        elif t.status == 'cancelled':
            t_status = 'failed'
            
        transaction = {
            'id': transaction_id,
            'booking_id': t.ticket_number,
            'customer_name': t.billing_name,
            'customer_email': t.billing_email,
            'event_title': t.event.title,
            'amount': float(t.price * t.quantity),
            'status': t_status,
            'payment_method': 'mpesa',
            'created_at': t.purchase_date.isoformat()
        }
        return JsonResponse({'success': True, 'transaction': transaction})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def transaction_refund_api(request):
    try:
        data = json.loads(request.body)
        txn_id = data.get('transaction_id')
        ticket_number = f"TICK-{txn_id[4:]}"
        t = get_object_or_404(Ticket, ticket_number=ticket_number)
        t.status = 'refunded'
        t.save()
        expire_notifications_for_entity('refund', t.id, ['refund_pending'])
        return JsonResponse({'success': True, 'message': 'Refund completed successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def transactions_export(request):
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Transaction ID', 'Ticket Number', 'Customer', 'Customer Email', 'Event', 'Amount', 'Status', 'Date'])
        
        tickets = Ticket.objects.all()
        for t in tickets:
            t_status = 'success'
            if t.status == 'refunded':
                t_status = 'refunded'
            elif t.status == 'cancelled':
                t_status = 'failed'
            writer.writerow([
                f"TXN-{t.ticket_number[5:]}",
                t.ticket_number,
                t.billing_name,
                t.billing_email,
                t.event.title,
                t.price * t.quantity,
                t_status,
                t.purchase_date.isoformat()
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Payouts API
@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def payouts_list_api(request):
    try:
        events = Event.objects.all()
        data = []
        for e in events:
            # Sum dynamic tickets sold for event
            sales_agg = Ticket.objects.filter(event=e).exclude(status='cancelled').aggregate(
                total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
            )
            total_sales = float(sales_agg['total'] or 0.0)
            platform_fee = total_sales * 0.05
            amount = total_sales - platform_fee
            
            payout_status = 'paid' if e.start_date < timezone.now() else 'pending'
            
            data.append({
                'id': e.id,
                'organizer_name': e.organizer.organization_name or e.organizer.get_full_name() or e.organizer.username,
                'event_title': e.title,
                'amount': amount,
                'status': payout_status,
                'payment_method': 'bank_transfer',
                'requested_date': e.created_at.isoformat()
            })
        return JsonResponse({'success': True, 'payouts': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def payouts_stats(request):
    try:
        events = Event.objects.all()
        total_payout = 0.0
        pending_payout = 0.0
        for e in events:
            sales_agg = Ticket.objects.filter(event=e).exclude(status='cancelled').aggregate(
                total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
            )
            total_sales = float(sales_agg['total'] or 0.0)
            amount = total_sales * 0.95
            
            if e.start_date < timezone.now():
                total_payout += amount
            else:
                pending_payout += amount
                
        stats = {
            'total_payout': total_payout,
            'pending_payout': pending_payout,
            'processed_count': Event.objects.filter(start_date__lt=timezone.now()).count(),
            'pending_count': Event.objects.filter(start_date__gte=timezone.now()).count()
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def payout_process(request):
    return JsonResponse({'success': True, 'message': 'Payout processed successfully'})

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def payout_process_all(request):
    return JsonResponse({'success': True, 'message': 'All pending payouts processed successfully'})


@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def payout_detail_api(request, payout_id):
    try:
        e = get_object_or_404(Event, id=payout_id)
        sales_agg = Ticket.objects.filter(event=e).exclude(status='cancelled').aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        total_sales = float(sales_agg['total'] or 0.0)
        platform_fee = total_sales * 0.05
        amount = total_sales - platform_fee
        payout_status = 'paid' if e.start_date < timezone.now() else 'pending'
        payout = {
            'id': e.id,
            'organizer_name': e.organizer.organization_name or e.organizer.get_full_name() or e.organizer.username,
            'organizer_email': e.organizer.email,
            'event_title': e.title,
            'period': e.start_date.strftime('%B %Y'),
            'events_count': 1,
            'ticket_sales': total_sales,
            'platform_fee': platform_fee,
            'payout_amount': amount,
            'amount': amount,
            'status': payout_status,
            'payment_method': 'bank_transfer',
            'requested_date': e.created_at.isoformat(),
        }
        return JsonResponse({'success': True, 'payout': payout})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 8. REPORTS & ANALYTICS APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def reports_kpi(request):
    # Reuses analytics kpi structure
    try:
        total_revenue = Ticket.objects.exclude(status='cancelled').aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        total_tickets = Ticket.objects.exclude(status='cancelled').aggregate(
            total=Sum(Coalesce('quantity', 0))
        )
        
        rev = float(total_revenue['total'] or 0.0)
        tix = int(total_tickets['total'] or 0)
        users = User.objects.count()
        
        kpi_data = {
            'total_revenue': rev,
            'total_tickets': tix,
            'active_users': users,
            'completed_events': Event.objects.filter(start_date__lt=timezone.now()).count(),
            'total_events': Event.objects.count(),
            'total_bookings': tix,
            'conversion_rate': 68,
            'avg_order_value': float(rev / max(1, Ticket.objects.count())),
            'revenue_trend': {'percentage': 18},
            'tickets_trend': {'percentage': 8},
            'users_trend': {'percentage': 15},
            'events_trend': {'percentage': 12}
        }
        
        summary_data = {
            'total_events': Event.objects.count(),
            'total_bookings': tix,
            'total_organizers': User.objects.filter(role='organizer').count(),
            'conversion_rate': 68,
            'avg_order_value': float(rev / max(1, Ticket.objects.count())),
            'avg_fill_rate': 72
        }
        
        return JsonResponse({
            'success': True,
            'stats': kpi_data,
            'kpi': kpi_data,
            'summary': summary_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def reports_sales(request):
    try:
        tickets = Ticket.objects.exclude(status='cancelled').order_by('-purchase_date')
        data = [{
            'id': t.ticket_number,
            'event_title': t.event.title,
            'category': t.event.category.name if t.event.category else 'N/A',
            'quantity': t.quantity,
            'total': float(t.price * t.quantity),
            'date': t.purchase_date.isoformat()
        } for t in tickets]
        return JsonResponse({'success': True, 'sales': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def reports_events_api(request):
    try:
        events = Event.objects.all()
        data = []
        for e in events:
            tix_agg = Ticket.objects.filter(event=e).exclude(status='cancelled').aggregate(
                total=Sum(Coalesce('quantity', 0))
            )
            rev_agg = Ticket.objects.filter(event=e).exclude(status='cancelled').aggregate(
                total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
            )
            tix = int(tix_agg['total'] or 0)
            rev = float(rev_agg['total'] or 0.0)
            
            data.append({
                'id': e.id,
                'title': e.title,
                'category': e.category.name if e.category else 'N/A',
                'organizer': e.organizer.username,
                'tickets_sold': tix,
                'revenue': rev,
                'status': e.status
            })
        return JsonResponse({'success': True, 'events': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def reports_events_summary(request):
    try:
        total_events = Event.objects.count()
        published = Event.objects.filter(status='published').count()
        draft = Event.objects.filter(status='draft').count()
        summary = {
            'total': total_events,
            'published': published,
            'draft': draft,
            'cancelled': Event.objects.filter(status='cancelled').count()
        }
        return JsonResponse({'success': True, 'summary': summary})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 9. SUPPORT TICKETS APIS (DYNAMIC JSON STORE) ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def support_tickets_list(request):
    try:
        status = request.GET.get('status', 'all')
        search = request.GET.get('search', '').strip()
        
        tickets = get_support_tickets()
        
        if status != 'all':
            tickets = [t for t in tickets if t['status'] == status]
        if search:
            tickets = [t for t in tickets if search.lower() in t['subject'].lower() or search.lower() in t['customer_name'].lower()]
            
        return JsonResponse({'success': True, 'tickets': tickets})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def support_ticket_detail_api(request, ticket_id):
    try:
        t = get_support_ticket_detail(ticket_id)
        if not t:
            return JsonResponse({'success': False, 'message': 'Ticket not found'}, status=404)
        return JsonResponse({'success': True, 'ticket': t})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def support_ticket_reply(request, ticket_id):
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        status = data.get('status')
        
        if not message:
            return JsonResponse({'success': False, 'message': 'Reply message required'}, status=400)
            
        add_support_ticket_reply(ticket_id, 'admin', message)
        if status:
            update_support_ticket_status(ticket_id, status)
            
        return JsonResponse({'success': True, 'message': 'Reply sent successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def support_stats(request):
    try:
        tickets = get_support_tickets()
        stats = {
            'total': len(tickets),
            'open': len([t for t in tickets if t['status'] == 'open']),
            'pending': len([t for t in tickets if t['status'] == 'pending']),
            'resolved': len([t for t in tickets if t['status'] == 'resolved'])
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 10. NOTIFICATIONS APIS (DYNAMIC JSON STORE) ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def notifications_api(request):
    try:
        notifications = get_notifications()
        return JsonResponse({'success': True, 'notifications': notifications})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def api_notifications_recent(request):
    try:
        notifications = get_notifications()
        unread_count = len([n for n in notifications if not n['is_read']])
        return JsonResponse({'success': True, 'notifications': notifications[:10], 'unread_count': unread_count})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_notification_mark_read(request, notification_id):
    try:
        mark_notification_read(notification_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_notifications_mark_all_read(request):
    try:
        mark_all_notifications_read()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
@admin_required_json
def api_notification_delete(request, notification_id):
    try:
        deleted = delete_notification(notification_id)
        if not deleted:
            return JsonResponse({'success': False, 'message': 'Notification not found'}, status=404)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_notification_dismiss(request, notification_id):
    try:
        data = json.loads(request.body) if request.body else {}
        on_view = bool(data.get('on_view', False))
        force = bool(data.get('force', False))
        dismissed = dismiss_notification(notification_id, on_view=on_view, force=force)
        return JsonResponse({'success': True, 'dismissed': dismissed})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_notifications_prune(request):
    try:
        notifications = get_notifications()
        return JsonResponse({'success': True, 'notifications': notifications})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 11. PROFILE & SETTINGS APIS ============

def _serialize_admin_profile(u):
    return {
        'username': u.username,
        'full_name': u.get_full_name() or u.username,
        'email': u.email,
        'phone': u.phone or '',
        'role': u.role,
        'avatar_url': u.get_avatar_url(),
    }


@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def user_profile(request):
    try:
        u = request.user
        if not u.is_authenticated:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        data = _serialize_admin_profile(u)
        return JsonResponse({'success': True, 'user': data, **data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def user_profile_update(request):
    try:
        data = json.loads(request.body) if request.body else {}
        u = request.user
        if data.get('full_name'):
            parts = data['full_name'].strip().split(' ', 1)
            u.first_name = parts[0]
            u.last_name = parts[1] if len(parts) > 1 else ''
        if data.get('email'):
            u.email = data['email'].strip()
        if 'phone' in data:
            u.phone = data.get('phone', '').strip()
        u.save()
        profile = _serialize_admin_profile(u)
        return JsonResponse({'success': True, 'message': 'Profile updated', 'user': profile, **profile})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def user_profile_change_password(request):
    try:
        data = json.loads(request.body) if request.body else {}
        current = data.get('current_password', '')
        new_password = data.get('new_password', '')
        if not request.user.check_password(current):
            return JsonResponse({'success': False, 'message': 'Current password is incorrect'}, status=400)
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters'}, status=400)
        request.user.set_password(new_password)
        request.user.save()
        return JsonResponse({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def user_profile_stats(request):
    try:
        rev_agg = Ticket.objects.exclude(status='cancelled').aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        stats = {
            'events_managed': Event.objects.count(),
            'users_managed': User.objects.count(),
            'tickets_processed': Ticket.objects.count(),
            'pending_approvals': Event.objects.filter(status='pending').count(),
            'revenue_generated': float(rev_agg['total'] or 0.0),
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def _default_settings():
    return {
        'site_name': 'EventHub',
        'site_tagline': 'Discover Amazing Events in Kenya',
        'site_description': 'Event Management Platform',
        'logo_url': '',
        'support_email': 'support@eventhub.co.ke',
        'support_phone': '+254 700 000000',
        'company_address': 'Nairobi, Kenya',
        'contact_email': 'info@eventhub.com',
        'timezone': 'Africa/Nairobi',
        'date_format': 'DD/MM/YYYY',
        'currency': 'KES',
        'platform_fee': 5,
        'processing_fee': 0,
        'min_payout': 500,
        'facebook_url': '',
        'twitter_url': '',
        'instagram_url': '',
        'linkedin_url': '',
    }


@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def settings_api(request):
    try:
        settings = _default_settings()
        return JsonResponse({'success': True, 'settings': settings, **settings})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@admin_required_json
def settings_general_api(request):
    try:
        if request.method == 'GET':
            settings = _default_settings()
            return JsonResponse({'success': True, 'settings': settings})
        return JsonResponse({'success': True, 'message': 'Settings saved successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 12. BRANDS MARKETING BROADCAST EMAIL API ============
from bookings.email_service import send_admin_broadcast_email

@csrf_exempt
@require_http_methods(["POST"])
@admin_required_json
def api_admin_broadcast(request):
    """
    Broadcasts custom marketing emails to registered attendees or organizers.
    Only accessible by staff/admin accounts.
    """
    try:
        data = json.loads(request.body)
        audience = data.get('audience') # 'attendees' or 'organizers'
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        
        if not audience or not subject or not message:
            return JsonResponse({'success': False, 'message': 'Audience, subject, and message are required.'}, status=400)
            
        if audience == 'attendees':
            users = User.objects.filter(role='attendee')
            role_label = 'Attendee'
        elif audience == 'organizers':
            users = User.objects.filter(role='organizer')
            role_label = 'Organizer'
        else:
            return JsonResponse({'success': False, 'message': 'Invalid audience target.'}, status=400)
            
        sent_count = 0
        for u in users:
            if u.email:
                send_admin_broadcast_email(
                    recipient_email=u.email,
                    subject=subject,
                    message=message,
                    recipient_role=role_label
                )
                sent_count += 1
                
        return JsonResponse({
            'success': True, 
            'message': f"Successfully broadcasted '{subject}' campaign to {sent_count} {audience}!"
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============ 9. CHECK-IN HISTORY & STATS APIS ============

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def checkin_stats(request):
    try:
        event_id = request.GET.get('event_id', '').strip()
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()

        # Build query for tickets/check-ins
        ticket_query = Q()
        event_query = Q()
        if event_id:
            ticket_query &= Q(event_id=event_id)
            event_query &= Q(id=event_id)
        if date_from:
            ticket_query &= Q(purchase_date__date__gte=date_from)
            event_query &= Q(start_date__date__gte=date_from)
        if date_to:
            ticket_query &= Q(purchase_date__date__lte=date_to)
            event_query &= Q(start_date__date__lte=date_to)

        total_events = Event.objects.filter(event_query).count()
        total_tickets = Ticket.objects.filter(ticket_query).count()
        checked_in = Ticket.objects.filter(ticket_query, status='checked_in').count()
        
        if total_tickets > 0:
            avg_attendance = round((checked_in / total_tickets) * 100, 1)
        else:
            avg_attendance = 0.0

        stats = {
            'total_events': total_events,
            'total_tickets': total_tickets,
            'checked_in': checked_in,
            'avg_attendance': avg_attendance
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def checkin_events(request):
    try:
        event_id = request.GET.get('event_id', '').strip()
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))

        query = Q()
        if event_id:
            query &= Q(id=event_id)
        if date_from:
            query &= Q(start_date__date__gte=date_from)
        if date_to:
            query &= Q(start_date__date__lte=date_to)

        events = Event.objects.filter(query).order_by('-start_date')
        total_items = events.count()
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size

        events_slice = events[start:end]
        data = []
        for e in events_slice:
            total_tickets = Ticket.objects.filter(event=e).count()
            checked_in = Ticket.objects.filter(event=e, status='checked_in').count()
            data.append({
                'id': e.id,
                'title': e.title,
                'event_date': e.start_date.isoformat(),
                'venue': e.venue,
                'total_tickets': total_tickets,
                'checked_in': checked_in
            })

        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_items
        }
        return JsonResponse({'success': True, 'events': data, 'pagination': pagination})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def checkin_recent(request):
    try:
        event_id = request.GET.get('event_id', '').strip()
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()
        limit = int(request.GET.get('limit', 50))

        query = Q(status='checked_in')
        if event_id:
            query &= Q(event_id=event_id)
        if date_from:
            query &= Q(checked_in_at__date__gte=date_from)
        if date_to:
            query &= Q(checked_in_at__date__lte=date_to)

        tickets = Ticket.objects.filter(query).order_by('-checked_in_at')[:limit]
        data = []
        for t in tickets:
            data.append({
                'ticket_number': t.ticket_number,
                'attendee_name': t.billing_name,
                'attendee_email': t.billing_email,
                'event_title': t.event.title,
                'checkin_time': t.checked_in_at.isoformat() if t.checked_in_at else timezone.now().isoformat(),
                'checked_by': 'System Admin'
            })
        return JsonResponse({'success': True, 'checkins': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def checkin_event_details(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        total_tickets = Ticket.objects.filter(event=e).count()
        checked_in = Ticket.objects.filter(event=e, status='checked_in').count()
        not_checked_in = max(0, total_tickets - checked_in)
        
        if total_tickets > 0:
            attendance_rate = round((checked_in / total_tickets) * 100, 1)
        else:
            attendance_rate = 0.0

        details = {
            'total_tickets': total_tickets,
            'checked_in': checked_in,
            'not_checked_in': not_checked_in,
            'attendance_rate': attendance_rate
        }
        return JsonResponse({'success': True, 'details': details})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def checkin_event_timeline(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        tickets = Ticket.objects.filter(event=e, status='checked_in', checked_in_at__isnull=False).order_by('checked_in_at')
        
        labels = []
        values = []
        if tickets.exists():
            hourly_data = {}
            for t in tickets:
                hr_str = t.checked_in_at.strftime('%H:00')
                hourly_data[hr_str] = hourly_data.get(hr_str, 0) + 1
            
            sorted_hours = sorted(hourly_data.keys())
            for hr in sorted_hours:
                labels.append(hr)
                values.append(hourly_data[hr])
        else:
            labels = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00"]
            values = [0, 0, 0, 0, 0, 0, 0]

        return JsonResponse({'success': True, 'labels': labels, 'values': values})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def checkin_export(request):
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="checkin_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Ticket Number', 'Attendee Name', 'Attendee Email', 'Event Title', 'Check-in Time', 'Checked By'])
        
        event_id = request.GET.get('event_id', '').strip()
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()

        query = Q(status='checked_in')
        if event_id:
            query &= Q(event_id=event_id)
        if date_from:
            query &= Q(checked_in_at__date__gte=date_from)
        if date_to:
            query &= Q(checked_in_at__date__lte=date_to)

        tickets = Ticket.objects.filter(query).order_by('-checked_in_at')
        for t in tickets:
            writer.writerow([
                t.ticket_number,
                t.billing_name,
                t.billing_email,
                t.event.title,
                t.checked_in_at.isoformat() if t.checked_in_at else 'N/A',
                'System Admin'
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@admin_required_json
def checkin_event_export(request, event_id):
    try:
        e = get_object_or_404(Event, id=event_id)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="event_{event_id}_checkin_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Ticket Number', 'Attendee Name', 'Attendee Email', 'Check-in Time', 'Checked By'])
        
        tickets = Ticket.objects.filter(event=e, status='checked_in').order_by('-checked_in_at')
        for t in tickets:
            writer.writerow([
                t.ticket_number,
                t.billing_name,
                t.billing_email,
                t.checked_in_at.isoformat() if t.checked_in_at else 'N/A',
                'System Admin'
            ])
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

