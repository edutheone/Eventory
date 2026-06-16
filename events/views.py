import json
import dateutil.parser
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.cache import cache_page

from events.models import Event
from accounts.models import User
from bookings.models import Ticket
from django.db.models import Sum, Avg

def home(request):
    return render(request, 'index.html')


def get_platform_stats():
    """
    Shared platform headline stats for public pages and APIs.
    """
    from reviews.models import EventReview

    events_hosted = Event.objects.exclude(status='draft').count()

    ticket_agg = Ticket.objects.exclude(status='cancelled').aggregate(total=Sum('quantity'))
    happy_attendees = ticket_agg['total'] or 0

    event_organizers = Event.objects.values('organizer').distinct().count()

    avg_rating = EventReview.objects.aggregate(avg=Avg('rating'))['avg']
    if avg_rating is not None:
        satisfaction_rate = round((float(avg_rating) / 5.0) * 100)
    else:
        satisfaction_rate = 0

    return {
        'events_hosted': events_hosted,
        'happy_attendees': happy_attendees,
        'event_organizers': event_organizers,
        'satisfaction_rate': satisfaction_rate,
    }


def homepage_view(request):
    events_count = Event.objects.filter(status='published').count()
    attendees_count = User.objects.filter(role='attendee').count()
    organizers_count = User.objects.filter(role='organizer').count()
    tickets_count = Ticket.objects.filter(status='valid').aggregate(Sum('quantity'))['quantity__sum'] or 0
    platform_stats = get_platform_stats()

    context = {
        'events_count': events_count,
        'attendees_count': attendees_count,
        'organizers_count': organizers_count,
        'tickets_count': tickets_count,
        'satisfaction_rate': platform_stats['satisfaction_rate'],
    }
    return render(request, 'attendee/pages/homepage/homepage.html', context)


def success_stories_view(request):
    return render(request, 'attendee/pages/success-stories.html', get_platform_stats())



def event_list(request):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Browse Events - EventHub</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container">
                <a class="navbar-brand" href="/">EventHub</a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/">Home</a>
                    <a class="nav-link" href="/admin">Admin</a>
                </div>
            </div>
        </nav>
        <main class="container mt-4">
            <h1>Browse Events</h1>
            <p class="lead">Published events will appear here once organizers start adding them.</p>
            <div class="alert alert-info">No events are available yet.</div>
        </main>
    </body>
    </html>
    """
    return HttpResponse(html)


def organizer_dashboard(request):
    # Support both logged-in organizer and anonymous views for easy local testing
    if request.user.is_authenticated:
        if hasattr(request.user, 'role') and request.user.role != 'organizer':
            return HttpResponseForbidden('You do not have permission to access the organizer dashboard.')

    return render(request, 'organizer_dashboard.html')

def organizer_dashboard_stats(request):
    from accounts.auth import authenticate_bearer
    
    user = request.user
    if not user.is_authenticated:
        bearer_user, error = authenticate_bearer(request)
        if bearer_user:
            user = bearer_user
        else:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
            
    if getattr(user, 'role', None) != 'organizer' and not user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    try:
        events = Event.objects.filter(organizer=user)
        events_count = events.count()
        
        from bookings.models import Ticket
        tickets = Ticket.objects.filter(event__organizer=user, status='valid')
        tickets_sold = sum(t.quantity for t in tickets)
        revenue = sum(t.quantity * t.price for t in tickets)
        
        # Calculate top event by tickets sold/revenue
        top_event_name = 'No events yet'
        if events_count > 0:
            event_revenues = []
            for e in events:
                e_revenue = sum(t.quantity * t.price for t in tickets.filter(event=e))
                event_revenues.append((e_revenue, e.title))
            if event_revenues:
                top_event_name = sorted(event_revenues, reverse=True)[0][1]
                
        revenue_value = float(revenue)
        attendees_count = tickets_sold

        metrics = {
            # Current keys used by organizer dashboard frontend
            'total_events': events_count,
            'total_tickets_sold': tickets_sold,
            'total_revenue': revenue_value,
            'total_attendees': attendees_count,
            # Backward-compatible keys used in other modules
            'events_count': events_count,
            'tickets_sold': tickets_sold,
            'revenue': revenue_value,
            'attendees': attendees_count,
            'top_event': top_event_name,
            'conversion_rate': 74 if events_count > 0 else 0,
            'new_followers': 32 if events_count > 0 else 0,
            'pending_payout': revenue_value * 0.85 if revenue > 0 else 0.00,
        }

        return JsonResponse(metrics)
    except Exception:
        # If the DB is temporarily unavailable (e.g. DATABASE_URL/Supabase outage),
        # return safe zeros so the dashboard remains usable.
        return JsonResponse({
            'total_events': 0,
            'total_tickets_sold': 0,
            'total_revenue': 0.0,
            'total_attendees': 0,
            'events_count': 0,
            'tickets_sold': 0,
            'revenue': 0.0,
            'attendees': 0,
            'top_event': 'Unavailable',
            'conversion_rate': 0,
            'new_followers': 0,
            'pending_payout': 0.0,
            'db_connected': False
        }, status=200)


def organizer_dashboard_revenue(request):
    from accounts.auth import authenticate_bearer
    from bookings.models import Ticket
    from django.utils import timezone
    from datetime import timedelta
    import datetime
    
    user = request.user
    if not user.is_authenticated:
        bearer_user, error = authenticate_bearer(request)
        if bearer_user:
            user = bearer_user
        else:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
            
    if getattr(user, 'role', None) != 'organizer' and not user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    period = request.GET.get('period', '12months')
    
    try:
        tickets = Ticket.objects.filter(event__organizer=user).exclude(status__in=['cancelled', 'refunded'])
        now = timezone.now()
        
        labels = []
        values = []
        
        if period == '7days':
            # Last 7 days (including today)
            for i in range(6, -1, -1):
                day = now - timedelta(days=i)
                day_tickets = tickets.filter(
                    purchase_date__year=day.year,
                    purchase_date__month=day.month,
                    purchase_date__day=day.day
                )
                revenue = sum(t.quantity * t.price for t in day_tickets)
                labels.append(day.strftime('%a'))
                values.append(float(revenue))
                
        elif period == '4weeks':
            # Last 4 weeks (ending today)
            for i in range(3, -1, -1):
                start_date = now - timedelta(days=(i+1)*7)
                end_date = now - timedelta(days=i*7)
                week_tickets = tickets.filter(purchase_date__gte=start_date, purchase_date__lt=end_date)
                revenue = sum(t.quantity * t.price for t in week_tickets)
                labels.append(f"Week {4-i}")
                values.append(float(revenue))
                
        elif period == 'ytd':
            # Year-to-Date monthly (from January of the current year to the current month)
            current_year = now.year
            current_month = now.month
            for m in range(1, current_month + 1):
                start_date = timezone.make_aware(datetime.datetime(current_year, m, 1))
                if m == 12:
                    end_date = timezone.make_aware(datetime.datetime(current_year + 1, 1, 1))
                else:
                    end_date = timezone.make_aware(datetime.datetime(current_year, m + 1, 1))
                    
                month_tickets = tickets.filter(purchase_date__gte=start_date, purchase_date__lt=end_date)
                revenue = sum(t.quantity * t.price for t in month_tickets)
                labels.append(datetime.date(current_year, m, 1).strftime('%b'))
                values.append(float(revenue))
                
        else:  # 12months (default)
            # Last 12 months rolling (ending in the current month)
            for i in range(11, -1, -1):
                target_month = now.month - i
                target_year = now.year
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1
                    
                start_date = timezone.make_aware(datetime.datetime(target_year, target_month, 1))
                if target_month == 12:
                    end_date = timezone.make_aware(datetime.datetime(target_year + 1, 1, 1))
                else:
                    end_date = timezone.make_aware(datetime.datetime(target_year, target_month + 1, 1))
                    
                month_tickets = tickets.filter(purchase_date__gte=start_date, purchase_date__lt=end_date)
                revenue = sum(t.quantity * t.price for t in month_tickets)
                labels.append(datetime.date(target_year, target_month, 1).strftime('%b'))
                values.append(float(revenue))
                
        return JsonResponse({
            'labels': labels,
            'values': values
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============ ATTENDEE EVENTS API ENDPOINTS ============

from django.db.models import Q, Case, When, Value, IntegerField
from .models import Category, Event


def _events_with_image_first(queryset):
    """Prioritize events that have a banner image, then soonest start date."""
    return queryset.annotate(
        _has_image=Case(
            When(Q(banner_image='') | Q(banner_image__isnull=True), then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('-_has_image', 'start_date')


def resolve_banner_image(value):
    """Return a browser-loadable banner URL for API responses."""
    if not value:
        return ''
    value = value.strip()
    if value.startswith(('data:', 'http://', 'https://', '/')):
        return value
    from django.conf import settings
    if value.startswith(settings.MEDIA_URL):
        return value
    return settings.MEDIA_URL + value.lstrip('/')

def api_event_list(request):
    """API endpoint to list and search events for attendees"""
    from django.core.cache import cache
    import hashlib

    query = request.GET.get('search', '').strip()
    category_id = request.GET.get('category', '').strip()
    city = request.GET.get('city', '').strip()
    ordering = request.GET.get('ordering', '').strip()
    if not ordering:
        ordering = request.GET.get('sort', '').strip()
    
    # Handle search from both list.html and search.html
    if not query:
        query = request.GET.get('q', '').strip()

    # Simple pagination
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 6))
    if 'limit' not in request.GET and ('q' in request.GET or 'search' in request.GET):
        limit = 200  # return all matches when searching so no result is hidden by pagination

    # Construct unique cache key based on query params
    params_str = f"search:{query}|cat:{category_id}|city:{city}|ord:{ordering}|page:{page}|limit:{limit}"
    cache_key = f"api_event_list_v2_{hashlib.md5(params_str.encode('utf-8')).hexdigest()}"

    # Try cache lookup first
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data)
        
    events = Event.objects.filter(status='published', end_date__gte=timezone.now()).select_related('category')
    
    if query:
        events = events.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(venue__icontains=query)
        )
        
    if category_id:
        # Support both numeric id and slug (front-end sends slug)
        if category_id.isdigit():
            events = events.filter(category_id=category_id)
        else:
            events = events.filter(category__slug=category_id)
        
    if city:
        events = events.filter(Q(address__icontains=city) | Q(venue__icontains=city))
        
    # Ordering
    if ordering == 'price_asc' or ordering == 'price':
        events = events.order_by('price')
    elif ordering == 'price_desc' or ordering == '-price':
        events = events.order_by('-price')
    elif ordering == 'date_desc' or ordering == '-date':
        events = events.order_by('-start_date')
    elif ordering == 'date_asc' or ordering == 'date':
        events = events.order_by('start_date')
    elif ordering == 'title':
        events = events.order_by('title')
    else:
        events = _events_with_image_first(events)
        
    start = (page - 1) * limit
    end = page * limit
    
    count = events.count()
    events_page = events[start:end]
    
    results = []
    for e in events_page:
        results.append({
            'id': e.id,
            'title': e.title,
            'slug': e.slug,
            'description': e.description,
            'date': e.start_date.isoformat(),
            'start_date': e.start_date.isoformat(),
            'end_date': e.end_date.isoformat(),
            'location': e.venue,
            'city': e.address or 'Nairobi',
            'venue': e.venue,
            'price': float(e.price),
            'min_price': float(e.price),
            'vip_price': float(e.vip_price) if e.vip_price is not None else None,
            'vvip_price': float(e.vvip_price) if e.vvip_price is not None else None,
            'total_seats': e.total_seats,
            'available_seats': e.available_seats,
            'available_tickets': e.available_seats,
            'image': resolve_banner_image(e.banner_image),
            'banner_image': resolve_banner_image(e.banner_image),
            'category': e.category.name if e.category else 'General',
            'category_name': e.category.name if e.category else 'General',
            'is_featured': e.is_featured,
        })
        
    response_data = {
        'success': True,
        'count': count,
        'total_count': count,
        'results': results,
        'events': results,
        'total_pages': (count + limit - 1) // limit
    }

    # Store in cache for 1 hour (3600 seconds)
    cache.set(cache_key, response_data, 3600)
    
    return JsonResponse(response_data)


@cache_page(300)
def api_category_list(request):
    """API endpoint to list categories"""
    from django.db.models import Count, Q
    categories = Category.objects.annotate(
        active_event_count=Count(
            'event',
            filter=Q(event__status='published', event__end_date__gte=timezone.now())
        )
    )
    results = []
    for c in categories:
        results.append({
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'icon': c.icon or 'globe',
            'event_count': c.active_event_count
        })
    return JsonResponse({'success': True, 'categories': results})


@cache_page(15)
def api_event_detail(request, event_id):
    """API endpoint to get detail of a single event"""
    try:
        e = Event.objects.select_related('category', 'organizer').prefetch_related('images').get(id=event_id)
        data = {
            'id': e.id,
            'title': e.title,
            'slug': e.slug,
            'description': e.description,
            'date': e.start_date.isoformat(),
            'start_date': e.start_date.isoformat(),
            'end_date': e.end_date.isoformat(),
            'location': e.venue,
            'city': e.address or 'Nairobi',
            'venue': e.venue,
            'price': float(e.price),
            'min_price': float(e.price),
            'vip_price': float(e.vip_price) if e.vip_price is not None else None,
            'vvip_price': float(e.vvip_price) if e.vvip_price is not None else None,
            'total_seats': e.total_seats,
            'available_seats': e.available_seats,
            'available_tickets': e.available_seats,
            'image': resolve_banner_image(e.banner_image),
            'banner_image': resolve_banner_image(e.banner_image),
            'category': e.category.name if e.category else 'General',
            'category_name': e.category.name if e.category else 'General',
            'is_featured': e.is_featured,
            'organizer_name': e.organizer.organization_name or e.organizer.username,
            'images': [img.url for img in e.images.all()],
        }
        return JsonResponse({'success': True, 'event': data})
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found'}, status=404)


from django.utils import timezone

def api_dashboard_stats(request):
    """API endpoint to get attendee dashboard stats"""
    from bookings.views import get_authenticated_attendee
    from bookings.models import Ticket
    from django.db.models import Sum, DecimalField
    from django.db.models.functions import Coalesce

    user = get_authenticated_attendee(request)
    
    # Calculate general upcoming published events (fallback)
    general_upcoming_count = Event.objects.filter(status='published', start_date__gte=timezone.now()).count()
    if general_upcoming_count == 0:
        general_upcoming_count = Event.objects.filter(status='published').count()

    if not user or not user.is_authenticated:
        # Fallback to guest stats so it doesn't crash if session is unauthenticated
        return JsonResponse({
            'total_tickets': 0,
            'total_spent': 0.0,
            'upcoming_events': general_upcoming_count,
            'reviews_written': 0,
            'tickets_trend': {'percentage': 0, 'direction': 'flat'},
            'spent_trend': {'percentage': 0, 'direction': 'flat'},
            'upcoming_trend': {'percentage': 0, 'direction': 'flat'},
            'reviews_trend': {'percentage': 0, 'direction': 'flat'}
        })

    # If the user is staff/admin, display platform-wide stats instead of 0 values
    if user.is_staff or user.is_superuser or getattr(user, 'role', None) == 'admin':
        all_tickets = Ticket.objects.exclude(status='cancelled')
        total_tickets = all_tickets.aggregate(total=Sum('quantity'))['total'] or 0
        
        revenue_data = all_tickets.aggregate(
            total=Sum(Coalesce('price', 0) * Coalesce('quantity', 1), output_field=DecimalField())
        )
        total_spent = float(revenue_data['total'] or 0.0)
        upcoming_events = general_upcoming_count
        # Simulated/calculated reviews based on bookings
        reviews_written = all_tickets.count() // 2 + 5
    else:
        # Query the logged-in user's active tickets
        user_tickets = Ticket.objects.filter(attendee=user, status__in=['valid', 'checked_in'])
        total_tickets = sum(t.quantity for t in user_tickets)
        total_spent = float(sum(t.quantity * t.price for t in user_tickets))
        
        # Count upcoming events that this specific user has tickets for
        user_upcoming_count = user_tickets.filter(event__end_date__gte=timezone.now()).values('event').distinct().count()
        upcoming_events = user_upcoming_count if user_upcoming_count > 0 else general_upcoming_count
        from reviews.models import EventReview
        reviews_written = EventReview.objects.filter(user=user).count()

    return JsonResponse({
        'total_tickets': total_tickets,
        'total_spent': total_spent,
        'upcoming_events': upcoming_events,
        'reviews_written': reviews_written,
        'tickets_trend': {'percentage': 12, 'direction': 'up'} if (user.is_staff or user.is_superuser) else {'percentage': 0, 'direction': 'flat'},
        'spent_trend': {'percentage': 18, 'direction': 'up'} if (user.is_staff or user.is_superuser) else {'percentage': 0, 'direction': 'flat'},
        'upcoming_trend': {'percentage': 5, 'direction': 'up'} if (user.is_staff or user.is_superuser) else {'percentage': 0, 'direction': 'flat'},
        'reviews_trend': {'percentage': 10, 'direction': 'up'} if (user.is_staff or user.is_superuser) else {'percentage': 0, 'direction': 'flat'}
    })

def api_dashboard_recommendations(request):
    """API endpoint to get recommended events (featured events)"""
    events = Event.objects.filter(status='published', end_date__gte=timezone.now(), is_featured=True).order_by('start_date')[:3]
    if not events.exists():
        events = Event.objects.filter(status='published', end_date__gte=timezone.now()).order_by('start_date')[:3]
        
    results = []
    for e in events:
        results.append({
            'id': e.id,
            'title': e.title,
            'date': e.start_date.isoformat(),
            'location': e.venue,
            'price': float(e.price),
            'image': resolve_banner_image(e.banner_image),
        })
    return JsonResponse(results, safe=False)

def api_dashboard_recent_activity(request):
    """API endpoint to get recent activity"""
    from bookings.views import get_authenticated_attendee
    from bookings.models import Ticket
    
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse([], safe=False)
        
    tickets = Ticket.objects.filter(attendee=user).select_related('event').order_by('-purchase_date')[:5]
    results = []
    for t in tickets:
        results.append({
            'id': t.id,
            'type': 'booking',
            'title': f"Booked ticket for {t.event.title}",
            'created_at': t.purchase_date.isoformat(),
            'action_url': f"/attendee/tickets/detail/?ticket={t.ticket_number}"
        })
    return JsonResponse(results, safe=False)

def api_tickets_upcoming(request):
    """API endpoint to get upcoming tickets"""
    return JsonResponse({'results': []})

@cache_page(3600)
def api_featured_events(request):
    """API endpoint to get featured events for the attendee homepage"""
    events = Event.objects.filter(status='published', end_date__gte=timezone.now(), is_featured=True).select_related('category').order_by('start_date')[:6]
    if not events.exists():
        events = Event.objects.filter(status='published', end_date__gte=timezone.now()).select_related('category').order_by('start_date')[:6]
        
    results = []
    for e in events:
        results.append({
            'id': e.id,
            'title': e.title,
            'description': e.description,
            'date': e.start_date.isoformat() if e.start_date else None,
            'start_date': e.start_date.isoformat() if e.start_date else None,
            'end_date': e.end_date.isoformat() if e.end_date else None,
            'location': e.venue,
            'venue': e.venue,
            'price': float(e.price),
            'image': resolve_banner_image(e.banner_image),
            'banner_image': resolve_banner_image(e.banner_image),
            'category': e.category.name if e.category else 'General',
            'category_name': e.category.name if e.category else 'General',
            'attendees_count': e.total_seats - e.available_seats,
            'tickets_left': e.available_seats,
        })
    return JsonResponse({'success': True, 'events': results})


@cache_page(60)
@require_http_methods(["GET"])
def api_platform_stats(request):
    """
    Public API endpoint — no authentication required.
    Returns platform-wide headline stats for public marketing pages.
    """
    stats = get_platform_stats()
    return JsonResponse({
        'success': True,
        **stats,
    })


import dateutil.parser
from bookings.models import Ticket
from bookings.email_service import send_attendee_review_request_email, send_organizer_performance_summary_email

def _process_expired_events_async(events_ids, client_dt):
    """Background task to run post-event email dispatches asynchronously"""
    from django.db import connection
    import logging
    logger = logging.getLogger(__name__)
    try:
        # Re-query inside thread to keep database sessions distinct
        events = Event.objects.filter(id__in=events_ids)
        processed_attendees_emails = 0
        processed_organizers_emails = 0
        
        for event in events:
            # 1. Dispatch attendee review requests
            if not event.attendee_reviews_sent:
                tickets = Ticket.objects.filter(event=event, status='valid')
                attendee_map = {}
                for ticket in tickets:
                    email = ticket.billing_email or (ticket.attendee.email if ticket.attendee else None)
                    name = ticket.billing_name or (ticket.attendee.username if ticket.attendee else 'Attendee')
                    if email:
                        attendee_map[email] = name
                        
                for email, name in attendee_map.items():
                    try:
                        send_attendee_review_request_email(
                            attendee_email=email,
                            attendee_name=name,
                            event_title=event.title,
                            event_id=event.id
                        )
                        processed_attendees_emails += 1
                    except Exception as email_exc:
                        logger.error("Failed to send review email to %s: %s", email, email_exc)
                        
                event.attendee_reviews_sent = True
                
            # 2. Dispatch organizer performance summary reports
            if not event.organizer_summary_sent:
                tickets = Ticket.objects.filter(event=event, status='valid')
                total_seats_sold = sum(t.quantity for t in tickets)
                total_revenue = float(sum(t.quantity * t.price for t in tickets))
                
                try:
                    send_organizer_performance_summary_email(
                        organizer_email=event.organizer.email,
                        organizer_name=event.organizer.organization_name or event.organizer.username,
                        event_title=event.title,
                        total_attendees=total_seats_sold,
                        total_revenue=total_revenue
                    )
                    processed_organizers_emails += 1
                except Exception as email_exc:
                    logger.error("Failed to send organizer summary email for event %d: %s", event.id, email_exc)
                event.organizer_summary_sent = True
                
            event.save()
            
        logger.info(
            "Async post-event alerts completed. Attendees notified: %d, Organizers notified: %d",
            processed_attendees_emails,
            processed_organizers_emails
        )
    except Exception as exc:
        logger.exception("Error in background post-event alerts thread: %s", exc)
    finally:
        connection.close()


@csrf_exempt
@require_http_methods(["POST"])
def api_events_check_expired(request):
    """
    Checks for completed events and dispatches automated post-event alerts in the background.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        data = json.loads(request.body)
        client_date = data.get('current_date')
        client_time = data.get('current_time', '00:00')
        
        if not client_date:
            return JsonResponse({'success': False, 'message': 'Date is required'}, status=400)
            
        # Parse client date and time context
        try:
            client_dt = dateutil.parser.isoparse(f"{client_date}T{client_time}")
            if timezone.is_naive(client_dt):
                client_dt = timezone.make_aware(client_dt)
        except ValueError:
            client_dt = timezone.now()

        # Query active published events that have passed this end datetime and need notification updates
        events_to_process = Event.objects.filter(
            status='published',
            end_date__lte=client_dt
        ).filter(
            Q(attendee_reviews_sent=False) | Q(organizer_summary_sent=False)
        )
        
        events_ids = list(events_to_process.values_list('id', flat=True))
        
        if events_ids:
            # Start background thread
            import threading
            thread = threading.Thread(
                target=_process_expired_events_async,
                args=(events_ids, client_dt),
                daemon=True
            )
            thread.start()
            message = f"Post-event automations triggered in the background for {len(events_ids)} events."
        else:
            message = "No events require processing."
            
        return JsonResponse({
            'success': True,
            'message': message,
        })
        
    except Exception as e:
        logger.error("Error in api_events_check_expired: %s", e)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Location-Based Event Discovery
# ---------------------------------------------------------------------------


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_discover_local_events(request):
    """
    POST /api/events/discover/

    Body (JSON):
      { "lat": -1.286389, "lng": 36.817223 }         # browser GPS
      OR
      { "location_text": "Nairobi" }                  # typed / profile fallback

    Response:
      {
        "success": true,
        "location": "Nairobi",
        "county": "Nairobi County",
        "location_source": "browser_geolocation" | "user_profile" | "ip_detection",
        "internal_count": <int>,
        "external_count": <int>,
        "internal_events": [ ... ],   # app DB events — ticket purchasing enabled
        "external_events": [ ... ]    # scraped events  — view-only
      }
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        from django.http import HttpResponse as _HR
        return _HR(status=204)

    import json as _json
    from django.db.models import Q
    from events.discovery import (
        resolve_county_from_coords,
        resolve_county_from_ip,
        normalize_county,
        discover_events_for_county,
    )

    # ---- Parse body ----
    try:
        data = _json.loads(request.body or "{}")
    except (_json.JSONDecodeError, Exception):
        data = {}

    # ---- Resolve county (3-level fallback) ----
    county: str | None = None
    location_source = "unknown"

    lat = data.get("lat")
    lng = data.get("lng")
    location_text = str(data.get("location_text") or "").strip()

    if lat is not None and lng is not None:
        try:
            county = resolve_county_from_coords(float(lat), float(lng))
            if county:
                location_source = "browser_geolocation"
        except (ValueError, TypeError):
            pass

    if not county and location_text:
        county = normalize_county(location_text)
        location_source = "user_profile"

    if not county:
        # Last resort: IP-based detection
        x_fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
        client_ip = x_fwd.split(",")[0].strip() if x_fwd else request.META.get("REMOTE_ADDR", "")
        county = resolve_county_from_ip(client_ip)
        location_source = "ip_detection"

    county = county or "Nairobi"

    # ---- Query internal (app) events ----
    now = timezone.now()
    internal_qs = (
        Event.objects.filter(
            status="published",
            end_date__gte=now,
        )
        .filter(
            Q(venue__icontains=county)
            | Q(address__icontains=county)
            | Q(title__icontains=county)
        )
        .select_related("category")
        .order_by("start_date")[:20]
    )

    internal_events = []
    for e in internal_qs:
        internal_events.append({
            "type": "internal",
            "id": e.id,
            "title": e.title,
            "start_date": e.start_date.isoformat(),
            "end_date": e.end_date.isoformat(),
            "venue": e.venue,
            "address": e.address,
            "price": float(e.price),
            "slug": e.slug,
            "banner_image": e.banner_image or "",
            "category": e.category.name if e.category else "General",
            "available_seats": e.available_seats,
            "status": e.status,
            "can_purchase": True,
            "detail_url": f"/events/detail/?id={e.id}",
        })

    # ---- Scrape external events in parallel ----
    external_events = discover_events_for_county(county)

    return JsonResponse({
        "success": True,
        "location": county,
        "county": f"{county} County",
        "location_source": location_source,
        "internal_count": len(internal_events),
        "external_count": len(external_events),
        "internal_events": internal_events,
        "external_events": external_events,
    })


def api_db_status(request):
    """Diagnostic view to inspect database engine, columns, and migrations status."""
    from django.conf import settings
    from django.db import connection
    
    db_engine = settings.DATABASES['default']['ENGINE']
    
    status_info = {
        'db_engine': db_engine,
        'connection_vendor': connection.vendor,
        'banner_image_column_type': None,
        'eventimage_image_column_type': None,
        'applied_migrations': [],
        'error': None
    }
    
    try:
        # 1. Fetch column info for events_event.banner_image
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute("""
                    SELECT data_type, character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'events_event' AND column_name = 'banner_image';
                """)
                row = cursor.fetchone()
                if row:
                    status_info['banner_image_column_type'] = f"{row[0]}({row[1]})" if row[1] else row[0]
                
                cursor.execute("""
                    SELECT data_type, character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'events_eventimage' AND column_name = 'image';
                """)
                row = cursor.fetchone()
                if row:
                    status_info['eventimage_image_column_type'] = f"{row[0]}({row[1]})" if row[1] else row[0]
            elif connection.vendor == 'sqlite':
                cursor.execute("PRAGMA table_info(events_event);")
                rows = cursor.fetchall()
                for r in rows:
                    if r[1] == 'banner_image':
                        status_info['banner_image_column_type'] = r[2]
                
                cursor.execute("PRAGMA table_info(events_eventimage);")
                rows = cursor.fetchall()
                for r in rows:
                    if r[1] == 'image':
                        status_info['eventimage_image_column_type'] = r[2]
                        
        # 2. Get applied migrations
        from django.db.migrations.recorder import MigrationRecorder
        applied = MigrationRecorder.Migration.objects.filter(app='events').values_list('name', flat=True)
        status_info['applied_migrations'] = list(applied)
        status_info['accounts_migrations'] = list(
            MigrationRecorder.Migration.objects.filter(app='accounts').values_list('name', flat=True)
        )

        from config.db_migrations import _auth_schema_status, _payment_schema_status
        status_info['auth_schema'] = _auth_schema_status()
        status_info['payment_schema'] = _payment_schema_status()
        status_info['payments_migrations'] = list(
            MigrationRecorder.Migration.objects.filter(app='payments').values_list('name', flat=True)
        )
        
    except Exception as e:
        status_info['error'] = str(e)
        
    return JsonResponse(status_info)


def api_run_migrations(request):
    """Diagnostic view to repair migration history and run Django migrations."""
    from config.db_migrations import run_migrations
    return JsonResponse(run_migrations())



