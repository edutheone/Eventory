import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Event, Category, EventImage
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage
from datetime import timedelta
import dateutil.parser

from accounts.auth import authenticate_bearer
from bookings.email_service import send_organizer_event_crud_email

from bookings.models import Ticket

def serialize_organizer_event(event):
    if hasattr(event, 'annotated_sold'):
        sold = event.annotated_sold
        revenue = float(event.annotated_revenue)
    else:
        tickets = Ticket.objects.filter(event=event, status='valid')
        sold = sum(t.quantity for t in tickets)
        revenue = float(sum(t.quantity * t.price for t in tickets))
        
    return {
        'id': event.id,
        'name': event.title,
        'title': event.title,
        'description': event.description,
        'category': event.category.name if event.category else 'General',
        'date': event.start_date.isoformat() if event.start_date else None,
        'start_date': event.start_date.isoformat() if event.start_date else None,
        'end_date': event.end_date.isoformat() if event.end_date else None,
        'location': event.venue,
        'venue': event.venue,
        'address': event.address,
        'capacity': event.total_seats,
        'price': float(event.price),
        'vip_price': float(event.vip_price) if event.vip_price is not None else None,
        'vvip_price': float(event.vvip_price) if event.vvip_price is not None else None,
        'sold': sold,
        'tickets_sold': sold,
        'revenue': revenue,
        'status': event.status,
        'image_url': event.banner_image or '',
        'images': [{'id': img.id, 'url': img.url} for img in event.images.all()]
    }

def organizer_required(view_func):
    """Decorator to ensure user is logged in and is an organizer."""
    def wrapper(request, *args, **kwargs):
        from accounts.auth import authenticate_bearer
        user = request.user
        if not user.is_authenticated:
            bearer_user, error = authenticate_bearer(request)
            if bearer_user:
                request.user = bearer_user
                user = bearer_user
            else:
                return JsonResponse({'success': False, 'message': 'Please login to continue'}, status=401)
        if getattr(user, 'role', None) != 'organizer' and not user.is_superuser:
            return JsonResponse({'success': False, 'message': 'Organizer access required'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_events_list(request):
    """List events for the logged-in organizer."""
    from django.db.models import Sum, F, DecimalField, OuterRef, Subquery
    from django.db.models.functions import Coalesce
    
    # Subqueries to pre-calculate ticket sales and revenue
    valid_tickets = Ticket.objects.filter(event=OuterRef('pk'), status='valid')
    sold_subquery = valid_tickets.values('event').annotate(total_sold=Sum('quantity')).values('total_sold')
    revenue_subquery = valid_tickets.values('event').annotate(
        total_rev=Sum(F('quantity') * F('price'), output_field=DecimalField())
    ).values('total_rev')
    
    events = Event.objects.filter(organizer=request.user).annotate(
        annotated_sold=Coalesce(Subquery(sold_subquery), 0),
        annotated_revenue=Coalesce(Subquery(revenue_subquery), 0, output_field=DecimalField())
    ).select_related('category').prefetch_related('images').order_by('-created_at')
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 12))
    paginator = Paginator(events, limit)
    if paginator.count == 0:
        return JsonResponse({
            'results': [],
            'page': 1,
            'page_size': limit,
            'count': 0,
            'total_pages': 0,
            'previous': False,
            'next': False
        })

    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    results = [serialize_organizer_event(e) for e in page_obj.object_list]
    return JsonResponse({
        'results': results,
        'page': page_obj.number,
        'page_size': page_obj.paginator.per_page,
        'count': paginator.count,
        'total_pages': paginator.num_pages,
        'previous': page_obj.has_previous(),
        'next': page_obj.has_next()
    })

@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def api_organizer_events_create(request):
    """Create a new event."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip() or data.get('title', '').strip()
        description = data.get('description', '').strip() or "A new event created from the organizer dashboard."
        date_str = data.get('date', '')
        if not date_str and data.get('start_date'):
            date_str = data.get('start_date').split('T')[0]
        start_time_str = data.get('startTime', '') or (data.get('start_date', '').split('T')[1] if 'T' in data.get('start_date', '') else '') or '00:00'
        end_time_str = data.get('endTime', '') or (data.get('end_date', '').split('T')[1] if 'T' in data.get('end_date', '') else '') or '00:00'
        venue = data.get('venue', '').strip() or data.get('location', '').strip()
        address = data.get('address', '').strip()
        capacity = int(data.get('capacity', 0))
        price = float(data.get('price', 0))
        
        vip_val = data.get('vip_price')
        vip_price = float(vip_val) if (vip_val is not None and str(vip_val).strip() != '') else None
        
        vvip_val = data.get('vvip_price')
        vvip_price = float(vvip_val) if (vvip_val is not None and str(vvip_val).strip() != '') else None
        
        image = data.get('image', '').strip() or data.get('banner_image', '').strip()
        category_name = data.get('category', 'Technology')
        status = data.get('status', 'draft')

        # Map frontend status to DB status
        db_status = 'pending'
            
        # Parse date and times
        try:
            start_date = dateutil.parser.isoparse(f"{date_str}T{start_time_str}")
            if timezone.is_naive(start_date):
                start_date = timezone.make_aware(start_date)
                
            end_date = dateutil.parser.isoparse(f"{date_str}T{end_time_str}")
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)
                
            if end_date <= start_date:
                end_date = start_date + timedelta(hours=3)
        except ValueError:
            start_date = timezone.now() + timedelta(days=7)
            end_date = start_date + timedelta(hours=3)
            
        # Get or create category
        slug_base = category_name.lower().replace(' ', '-')
        category, created = Category.objects.get_or_create(
            name=category_name,
            defaults={'slug': slug_base}
        )

        event = Event.objects.create(
            title=name,
            description=description,
            category=category,
            organizer=request.user,
            start_date=start_date,
            end_date=end_date,
            venue=venue,
            address=address,
            price=price,
            vip_price=vip_price,
            vvip_price=vvip_price,
            total_seats=capacity,
            available_seats=capacity,
            banner_image=image,
            status=db_status
        )

        try:
            details_str = f"{event.start_date.strftime('%B %d, %Y')} at {event.venue}"
            send_organizer_event_crud_email(
                organizer_email=request.user.email,
                organizer_name=request.user.username,
                event_title=event.title,
                action='created',
                details=details_str
            )
        except Exception as email_err:
            print("Failed to dispatch organizer CRUD email:", email_err)

        return JsonResponse(serialize_organizer_event(event))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_events_detail(request, event_id):
    """Get details for a specific organizer event."""
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
        return JsonResponse(serialize_organizer_event(event))
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found'}, status=404)

@csrf_exempt
@organizer_required
@require_http_methods(["PUT"])
def api_organizer_events_update(request, event_id):
    """Update an existing event."""
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
        data = json.loads(request.body)
        
        if 'name' in data:
            event.title = data['name'].strip()
        if 'title' in data:
            event.title = data['title'].strip()
        if 'description' in data:
            event.description = data['description'].strip()
        if 'category' in data:
            category_name = data['category'].strip() or 'General'
            slug_base = category_name.lower().replace(' ', '-')
            category, created = Category.objects.get_or_create(
                name=category_name,
                defaults={'slug': slug_base}
            )
            event.category = category
        if 'location' in data:
            event.venue = data['location'].strip()
        if 'venue' in data:
            event.venue = data['venue'].strip()
        if 'address' in data:
            event.address = data['address'].strip()
        if 'capacity' in data:
            new_cap = int(data['capacity'])
            diff = new_cap - event.total_seats
            event.total_seats = new_cap
            event.available_seats += diff
        if 'price' in data:
            event.price = float(data['price'])
        if 'vip_price' in data:
            vip_val = data['vip_price']
            event.vip_price = float(vip_val) if (vip_val is not None and str(vip_val).strip() != '') else None
        if 'vvip_price' in data:
            vvip_val = data['vvip_price']
            event.vvip_price = float(vvip_val) if (vvip_val is not None and str(vvip_val).strip() != '') else None
        if 'date' in data or 'start_date' in data:
            date_str = data.get('date', '') or data.get('start_date', '').split('T')[0]
            start_time_str = data.get('startTime', '') or (data.get('start_date', '').split('T')[1] if 'T' in data.get('start_date', '') else '')
            if date_str and start_time_str:
                try:
                    event.start_date = dateutil.parser.isoparse(f"{date_str}T{start_time_str}")
                    if timezone.is_naive(event.start_date):
                        event.start_date = timezone.make_aware(event.start_date)
                except ValueError:
                    pass
        if 'endTime' in data or 'end_date' in data:
            end_time_str = data.get('endTime', '') or (data.get('end_date', '').split('T')[1] if 'T' in data.get('end_date', '') else '')
            try:
                end_date_input = data.get('end_date', '') or data.get('date', '')
                if end_date_input and end_time_str:
                    event.end_date = dateutil.parser.isoparse(f"{end_date_input}T{end_time_str}")
                    if timezone.is_naive(event.end_date):
                        event.end_date = timezone.make_aware(event.end_date)
            except ValueError:
                pass
        if 'status' in data:
            status = data['status']
            if status in ('published', 'active'):
                if event.status in ('approved', 'published'):
                    event.status = 'published'
                else:
                    event.status = 'pending'
            elif status == 'cancelled':
                event.status = 'cancelled'
            elif status == 'pending':
                event.status = 'pending'
            else:
                event.status = 'draft'
            
        event.save()
        
        try:
            details_str = f"{event.start_date.strftime('%B %d, %Y')} at {event.venue}"
            send_organizer_event_crud_email(
                organizer_email=request.user.email,
                organizer_name=request.user.username,
                event_title=event.title,
                action='edited',
                details=details_str
            )
        except Exception as email_err:
            print("Failed to dispatch organizer CRUD email:", email_err)

        return JsonResponse({'success': True, 'message': 'Event updated successfully'})
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
@organizer_required
@require_http_methods(["DELETE"])
def api_organizer_events_delete(request, event_id):
    """Delete an event."""
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
        title = event.title
        event.delete()
        
        try:
            send_organizer_event_crud_email(
                organizer_email=request.user.email,
                organizer_name=request.user.username,
                event_title=title,
                action='deleted',
                details=None
            )
        except Exception as email_err:
            print("Failed to dispatch organizer CRUD email:", email_err)

        return JsonResponse({'success': True, 'message': 'Event deleted successfully'})
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


# ============ ORGANIZER SETTINGS VIEWS ============

@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_settings_general(request):
    """Retrieve General settings for the logged-in organizer."""
    user = request.user
    return JsonResponse({
        'organization_name': user.organization_name,
        'email': user.email,
        'phone': user.phone,
        'website': user.website,
        'bio': user.bio
    })

@csrf_exempt
@organizer_required
@require_http_methods(["PUT"])
def api_organizer_settings_general_update(request):
    """Update General settings for the logged-in organizer."""
    try:
        user = request.user
        data = json.loads(request.body)
        
        if 'organization_name' in data:
            user.organization_name = data['organization_name'].strip()
        if 'email' in data:
            user.email = data['email'].strip()
        if 'phone' in data:
            user.phone = data['phone'].strip()
        if 'website' in data:
            user.website = data['website'].strip()
        if 'bio' in data:
            user.bio = data['bio'].strip()
            
        user.save()
        return JsonResponse({'success': True, 'message': 'General settings saved successfully!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_settings_mpesa(request):
    """Retrieve M-Pesa payment profile for the logged-in organizer."""
    user = request.user
    return JsonResponse({
        'mpesa_display_name': user.mpesa_display_name,
        'mpesa_paybill': user.mpesa_paybill,
        'mpesa_till': user.mpesa_till,
        'mpesa_pochi': user.mpesa_pochi,
        'mpesa_send_money': user.mpesa_send_money,
        'is_configured': user.has_mpesa_payment_config(),
    })


@csrf_exempt
@organizer_required
@require_http_methods(["PUT"])
def api_organizer_settings_mpesa_update(request):
    """Update M-Pesa payment profile for the logged-in organizer."""
    try:
        user = request.user
        data = json.loads(request.body)

        if 'mpesa_display_name' in data:
            user.mpesa_display_name = data['mpesa_display_name'].strip()
        if 'mpesa_paybill' in data:
            user.mpesa_paybill = data['mpesa_paybill'].strip()
        if 'mpesa_till' in data:
            user.mpesa_till = data['mpesa_till'].strip()
        if 'mpesa_pochi' in data:
            user.mpesa_pochi = data['mpesa_pochi'].strip()
        if 'mpesa_send_money' in data:
            user.mpesa_send_money = data['mpesa_send_money'].strip()

        has_number = any([
            user.mpesa_paybill.strip(),
            user.mpesa_till.strip(),
            user.mpesa_pochi.strip(),
            user.mpesa_send_money.strip(),
        ])
        if not user.mpesa_display_name.strip():
            return JsonResponse({'success': False, 'message': 'M-Pesa display name is required.'}, status=400)
        if not has_number:
            return JsonResponse({
                'success': False,
                'message': 'At least one payment number (Paybill, Till, Pochi, or Send Money) is required.',
            }, status=400)

        user.save()
        return JsonResponse({'success': True, 'message': 'M-Pesa payment settings saved successfully!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_payouts_settings(request):
    """Retrieve payouts settlement credentials for the organizer."""
    user = request.user
    return JsonResponse({
        'account_number': user.account_number,
        'bank_name': user.bank_name,
        'account_holder': user.account_holder,
        'routing_number': user.routing_number
    })

@csrf_exempt
@organizer_required
@require_http_methods(["PUT"])
def api_organizer_payouts_settings_update(request):
    """Update payouts settlement credentials for the organizer."""
    try:
        user = request.user
        data = json.loads(request.body)
        
        if 'account_number' in data:
            user.account_number = data['account_number'].strip()
        if 'bank_name' in data:
            user.bank_name = data['bank_name'].strip()
        if 'account_holder' in data:
            user.account_holder = data['account_holder'].strip()
        if 'routing_number' in data:
            user.routing_number = data['routing_number'].strip()
            
        user.save()
        return JsonResponse({'success': True, 'message': 'Payment Settlement settings updated!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_settings_team(request):
    """List team members for the organizer."""
    from accounts.models import TeamMember
    members = TeamMember.objects.filter(organizer=request.user).order_by('created_at')
    results = []
    for m in members:
        results.append({
            'id': m.id,
            'email': m.email,
            'role': m.role
        })
    return JsonResponse(results, safe=False)

@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def api_organizer_settings_team_add(request):
    """Invite/add a new team member."""
    try:
        user = request.user
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        role = data.get('role', 'viewer').strip()
        
        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required'}, status=400)
            
        from accounts.models import TeamMember
        if TeamMember.objects.filter(organizer=user, email__iexact=email).exists():
            return JsonResponse({'success': False, 'message': 'Member already in team'}, status=400)
            
        import uuid
        member_id = uuid.uuid4().hex[:8]
        
        TeamMember.objects.create(
            id=member_id,
            organizer=user,
            email=email,
            role=role
        )
        
        return JsonResponse({'success': True, 'message': 'Team member invited!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
@organizer_required
@require_http_methods(["DELETE"])
def api_organizer_settings_team_remove(request, member_id):
    """Remove a team member."""
    try:
        user = request.user
        from accounts.models import TeamMember
        try:
            m = TeamMember.objects.get(id=member_id, organizer=user)
            m.delete()
            return JsonResponse({'success': True, 'message': 'Team member removed'})
        except TeamMember.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Member not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_settings_apikeys(request):
    """List developer API keys."""
    from accounts.models import ApiKey
    keys = ApiKey.objects.filter(organizer=request.user).order_by('created_at')
    results = []
    for k in keys:
        results.append({
            'id': k.id,
            'name': k.name,
            'key': k.key,
            'created_at': k.created_at.isoformat()
        })
    return JsonResponse(results, safe=False)

@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def api_organizer_settings_apikeys_create(request):
    """Generate a new developer API key."""
    try:
        user = request.user
        data = json.loads(request.body)
        name = data.get('name', 'Developer Key').strip()
        
        import uuid
        key_id = uuid.uuid4().hex[:8]
        secret_key = f"eh_live_{uuid.uuid4().hex}"
        
        from accounts.models import ApiKey
        k = ApiKey.objects.create(
            id=key_id,
            organizer=user,
            name=name,
            key=secret_key
        )
        
        return JsonResponse({
            'id': k.id,
            'name': k.name,
            'key': k.key,
            'created_at': k.created_at.isoformat()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
@organizer_required
@require_http_methods(["DELETE"])
def api_organizer_settings_apikeys_revoke(request, key_id):
    """Revoke a developer API key."""
    try:
        user = request.user
        from accounts.models import ApiKey
        try:
            k = ApiKey.objects.get(id=key_id, organizer=user)
            k.delete()
            return JsonResponse({'success': True, 'message': 'API Key revoked'})
        except ApiKey.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'API Key not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_reviews_stats(request):
    """
    Organizer reviews stats endpoint.
    Reviews app currently has no persisted model, so return safe defaults.
    """
    return JsonResponse({
        'avg_rating': 0,
        'total_reviews': 0,
        'response_rate': 0
    })


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_event_analytics(request, event_id):
    """Get analytics for a specific organizer event."""
    try:
        from django.utils import timezone
        from django.db.models.functions import TruncDate
        from django.db.models import Sum
        
        event = Event.objects.get(id=event_id, organizer=request.user)
        
        # Pull real, factual database tickets
        tickets = Ticket.objects.filter(event=event)
        valid_tickets = tickets.exclude(status__in=['cancelled', 'refunded'])
        
        tickets_sold = sum(t.quantity for t in valid_tickets)
        revenue = float(sum(t.quantity * t.price for t in valid_tickets))
        attendance = tickets.filter(status='checked_in').count()
        
        # Calculate sales data by day
        sales_by_day = (
            valid_tickets
            .annotate(date=TruncDate('purchase_date'))
            .values('date')
            .annotate(sold=Sum('quantity'))
            .order_by('date')
        )
        
        sales_data = []
        for s in sales_by_day:
            if s['date']:
                sales_data.append({
                    'date': s['date'].isoformat(),
                    'sold': s['sold']
                })
        
        # If sales data is empty, put a single entry for today or date of creation
        if not sales_data:
            sales_data.append({
                'date': timezone.now().date().isoformat(),
                'sold': 0
            })
            
        # Calculate ticket type distribution
        distribution = {}
        for t in valid_tickets:
            ttype = t.ticket_type or 'Regular'
            distribution[ttype] = distribution.get(ttype, 0) + t.quantity
            
        return JsonResponse({
            'total_tickets': event.total_seats or 100,
            'tickets_sold': tickets_sold,
            'attendance': attendance,
            'revenue': revenue,
            'sales_data': sales_data,
            'ticket_distribution': distribution
        })
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'}

MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
}

def validate_uploaded_file(file):
    if not file or not getattr(file, 'name', None):
        return False, "Invalid file object."
    # Check extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file extension: {ext}. Allowed types: PNG, JPEG, SVG, WEBP, GIF."
    
    # Check size (max 5MB)
    if file.size > 5 * 1024 * 1024:
        return False, "File is too large. Max size is 5MB."
        
    return True, None


def _file_to_base64_uri(file, ext):
    """Read an uploaded file and return a base64-encoded data URI string."""
    import base64
    mime = MIME_TYPES.get(ext, 'application/octet-stream')
    file.seek(0)
    encoded = base64.b64encode(file.read()).decode('utf-8')
    return f"data:{mime};base64,{encoded}"


@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def api_organizer_upload_image(request, event_id):
    """Upload a banner image for the event.

    Strategy:
      1. Try to save the file to the local filesystem via default_storage.
      2. If that fails (e.g. Vercel read-only FS), encode the file as a base64
         data URI stored directly in the EventImage TextField.
      3. Always attempt to persist the URL in event.banner_image, but catch any
         DataError gracefully (e.g. if the DB column is still VARCHAR(200) and
         migration 0005 hasn't run yet) – the EventImage record is the source of
         truth either way.
    """
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
        if 'image' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No image file uploaded.'}, status=400)

        file = request.FILES['image']
        is_valid, err_msg = validate_uploaded_file(file)
        if not is_valid:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)

        from django.conf import settings
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        import uuid

        ext = os.path.splitext(file.name)[1].lower()
        filename = f"banner_{event_id}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join('events', 'banners', filename)

        # Try filesystem save first; fall back to base64 data URI on read-only environments
        image_value = None  # stored in EventImage.image (TEXT – always safe)
        url = None          # returned to the browser and saved in event.banner_image
        try:
            file.seek(0)
            saved_path = default_storage.save(filepath, ContentFile(file.read()))
            url = settings.MEDIA_URL + saved_path.replace('\\', '/')
            image_value = saved_path  # relative path – EventImage.url property will prepend MEDIA_URL
        except Exception as storage_err:
            print("Storage save failed, using base64 fallback:", storage_err)
            data_uri = _file_to_base64_uri(file, ext)
            url = data_uri
            image_value = data_uri  # store the full data URI directly in the TEXT column

        # Persist the image record
        db_saved = False
        try:
            EventImage.objects.create(event=event, image=image_value)
            db_saved = True
        except Exception as db_err:
            print("Failed to save to EventImage table:", db_err)

        # Update event.banner_image – wrap in its own try-except because the column
        # may still be VARCHAR(200) on production if migration 0005 hasn't run yet.
        banner_saved = False
        try:
            event.banner_image = url
            event.save(update_fields=['banner_image'])
            banner_saved = True
        except Exception as banner_err:
            print("Could not save banner_image to event (possible column length issue):", banner_err)
            # Do NOT truncate base64 data URIs! They are useless when truncated.
            # Only attempt a short-URL fallback if it is a normal URL (starts with http or static path).
            if url and not url.startswith('data:'):
                try:
                    short_url = url[:190] if len(url) > 190 else url
                    event.banner_image = short_url
                    event.save(update_fields=['banner_image'])
                    banner_saved = True
                except Exception:
                    pass

        # If we failed to save the image anywhere due to database schema limitations, return a descriptive error
        if not db_saved and not banner_saved:
            return JsonResponse({
                'success': False,
                'message': 'Failed to save event image to the database due to schema limits. Please run migrations on Supabase by visiting: https://events-system-sable.vercel.app/api/events/run-migrations/'
            }, status=400)

        return JsonResponse({'success': True, 'image_url': url, 'image': url})
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def api_organizer_upload_gallery(request, event_id):
    """Upload multiple gallery images for the event.
    
    Falls back to base64 data URIs when the filesystem is read-only.
    """
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
        
        files = []
        if 'gallery' in request.FILES:
            files = request.FILES.getlist('gallery')
        else:
            for key in request.FILES:
                files.extend(request.FILES.getlist(key))
            
        if not files:
            return JsonResponse({'success': False, 'message': 'No gallery images uploaded.'}, status=400)
            
        # Validate all files first
        for file in files:
            is_valid, err_msg = validate_uploaded_file(file)
            if not is_valid:
                return JsonResponse({'success': False, 'message': f"File '{file.name}': {err_msg}"}, status=400)

        from django.conf import settings
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        import uuid

        saved_images = []
        for file in files:
            ext = os.path.splitext(file.name)[1].lower()
            filename = f"gallery_{event_id}_{uuid.uuid4().hex[:8]}{ext}"
            filepath = os.path.join('events', 'gallery', filename)
            try:
                file.seek(0)
                saved_path = default_storage.save(filepath, ContentFile(file.read()))
                image_value = saved_path
            except Exception:
                image_value = _file_to_base64_uri(file, ext)

            try:
                img_obj = EventImage.objects.create(event=event, image=image_value)
                saved_images.append({'id': img_obj.id, 'url': img_obj.url})
            except Exception as db_err:
                return JsonResponse({
                    'success': False,
                    'message': f"Failed to save gallery image to database: {str(db_err)}. Please run migrations by visiting: https://events-system-sable.vercel.app/api/events/run-migrations/"
                }, status=400)
            
        return JsonResponse({'success': True, 'images': saved_images})
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@organizer_required
@require_http_methods(["DELETE"])
def api_organizer_delete_gallery_image(request, event_id, image_id):
    """Delete a specific gallery image."""
    try:
        event = Event.objects.get(id=event_id, organizer=request.user)
        img_obj = EventImage.objects.get(id=image_id, event=event)
        
        # If the stored value is a filesystem path (not a data URI or external URL),
        # attempt to remove the physical file from storage.
        img_val = img_obj.image or ''
        if img_val and not img_val.startswith('data:') and not img_val.startswith('http'):
            try:
                from django.core.files.storage import default_storage
                if default_storage.exists(img_val):
                    default_storage.delete(img_val)
            except Exception as del_err:
                print("Could not delete image file from storage:", del_err)

        img_obj.delete()
        return JsonResponse({'success': True, 'message': 'Gallery image deleted successfully.'})
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found.'}, status=404)
    except EventImage.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Gallery image not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


