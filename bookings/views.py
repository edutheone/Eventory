import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from events.models import Event
from .models import Ticket
from .email_service import send_ticket_confirmation
from accounts.auth import authenticate_bearer
from django.utils import timezone

User = get_user_model()

def get_authenticated_attendee(request):
    """Resolve the logged-in attendee user from request session or bearer token."""
    user = request.user
    if not user.is_authenticated:
        bearer_user, error = authenticate_bearer(request)
        if bearer_user:
            user = bearer_user
    return user

@csrf_exempt
@require_http_methods(["POST"])
def ticket_checkout_api(request):
    """
    Legacy checkout endpoint — requires a completed PaymentOrder reference.
    Direct ticket creation without verified payment is no longer allowed.
    """
    try:
        data = json.loads(request.body)
        payment_order_id = data.get('payment_order_id')
        if not payment_order_id:
            return JsonResponse({
                'success': False,
                'message': 'A verified payment order is required. Use /api/attendee/payment-orders/create/.',
            }, status=400)

        from payments.models import PaymentOrder
        from bookings.services import fulfill_payment_order, FulfillmentError

        user = get_authenticated_attendee(request)
        if not user or not user.is_authenticated:
            return JsonResponse({'success': False, 'message': 'Please login to complete checkout.'}, status=401)

        try:
            order = PaymentOrder.objects.select_related('event', 'organizer', 'ticket').get(
                pk=payment_order_id, attendee=user,
            )
        except PaymentOrder.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Payment order not found.'}, status=404)

        if order.ticket_id:
            return JsonResponse({
                'success': True,
                'message': 'Checkout already completed.',
                'ticket_number': order.ticket.ticket_number,
            })

        fulfillable_statuses = {
            'pending_payment', 'failed', 'manual_review', 'verifying', 'completed',
        }
        if order.status not in fulfillable_statuses:
            return JsonResponse({
                'success': False,
                'message': f'Order cannot be fulfilled in its current state ({order.status}).',
            }, status=400)

        try:
            ticket = fulfill_payment_order(order)
        except FulfillmentError as exc:
            return JsonResponse({'success': False, 'message': exc.message}, status=400)

        return JsonResponse({
            'success': True,
            'message': 'Checkout successful! Ticket registered.',
            'ticket_number': ticket.ticket_number,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_tickets_upcoming(request):
    """API endpoint to get upcoming tickets for the logged-in attendee"""
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login to view tickets.'}, status=401)
        
    # Get tickets for events starting now or in the future
    tickets = Ticket.objects.filter(attendee=user, event__end_date__gte=timezone.now()).select_related('event').order_by('event__start_date')
    results = []
    for t in tickets:
        results.append({
            'ticket_number': t.ticket_number,
            'status': t.status,
            'ticket_type': t.ticket_type,
            'quantity': t.quantity,
            'price': float(t.price),
            'purchase_date': t.purchase_date.isoformat(),
            'event': {
                'id': t.event.id,
                'title': t.event.title,
                'start_date': t.event.start_date.isoformat(),
                'end_date': t.event.end_date.isoformat(),
                'venue_name': t.event.venue,
                'location': t.event.venue,
                'banner_image': t.event.banner_image,
            }
        })
    return JsonResponse({'results': results})

@csrf_exempt
@require_http_methods(["GET"])
def api_tickets_past(request):
    """API endpoint to get past tickets for the logged-in attendee"""
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login to view tickets.'}, status=401)
        
    # Get tickets for events that have ended
    tickets = Ticket.objects.filter(attendee=user, event__end_date__lt=timezone.now()).select_related('event').order_by('-event__start_date')
    results = []
    for t in tickets:
        results.append({
            'ticket_number': t.ticket_number,
            'status': t.status,
            'ticket_type': t.ticket_type,
            'quantity': t.quantity,
            'price': float(t.price),
            'purchase_date': t.purchase_date.isoformat(),
            'event': {
                'id': t.event.id,
                'title': t.event.title,
                'start_date': t.event.start_date.isoformat(),
                'end_date': t.event.end_date.isoformat(),
                'venue_name': t.event.venue,
                'location': t.event.venue,
                'banner_image': t.event.banner_image,
            }
        })
    return JsonResponse({'results': results})

@csrf_exempt
@require_http_methods(["GET"])
def api_ticket_detail(request, ticket_number):
    """API endpoint to get ticket detail"""
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)
        
    try:
        t = Ticket.objects.select_related('event').get(ticket_number=ticket_number, attendee=user)
        data = {
            'ticket_number': t.ticket_number,
            'status': t.status,
            'ticket_type': t.ticket_type,
            'quantity': t.quantity,
            'price': float(t.price),
            'purchase_date': t.purchase_date.isoformat(),
            'checked_in_at': t.checked_in_at.isoformat() if t.checked_in_at else None,
            'attendee_name': t.billing_name,
            'event': {
                'id': t.event.id,
                'title': t.event.title,
                'start_date': t.event.start_date.isoformat(),
                'end_date': t.event.end_date.isoformat(),
                'venue_name': t.event.venue,
                'location': t.event.venue,
                'banner_image': t.event.banner_image,
            }
        }
        return JsonResponse(data)
    except Ticket.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Ticket not found.'}, status=404)

@csrf_exempt
@require_http_methods(["GET"])
def api_ticket_qr(request, ticket_number):
    """API endpoint to get QR code for a ticket"""
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)
        
    try:
        t = Ticket.objects.get(ticket_number=ticket_number, attendee=user)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={t.ticket_number}"
        return JsonResponse({
            'success': True,
            'qr_code_url': qr_url
        })
    except Ticket.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Ticket not found.'}, status=404)

@csrf_exempt
@require_http_methods(["GET"])
def api_ticket_download(request, ticket_number):
    """API endpoint to download ticket"""
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
        
    try:
        t = Ticket.objects.select_related('event', 'event__organizer').get(ticket_number=ticket_number, attendee=user)
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Plus Jakarta Sans', Arial, sans-serif; background: #f8fafc; color: #0f172a; padding: 40px; }}
                .ticket {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border: 1px solid #e2e8f0; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #ff6b00, #ff8c3a); color: #ffffff; padding: 24px; text-align: center; }}
                .content {{ padding: 32px; }}
                .title {{ font-size: 24px; font-weight: 700; margin-bottom: 8px; }}
                .details {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 24px 0; border-top: 1px solid #f1f5f9; border-bottom: 1px solid #f1f5f9; padding: 16px 0; }}
                .label {{ color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
                .value {{ font-weight: 600; font-size: 15px; margin-top: 4px; }}
                .qr {{ text-align: center; margin-top: 24px; }}
                .qr img {{ width: 180px; height: 180px; }}
            </style>
        </head>
        <body>
            <div class="ticket">
                <div class="header">
                    <h2>EVENT TICKET</h2>
                    <div style="font-size: 14px; opacity: 0.9;">Ticket Number: {t.ticket_number}</div>
                </div>
                <div class="content">
                    <div class="title">{t.event.title}</div>
                    <div style="color: #64748b; font-size: 14px;">Hosted by {t.event.organizer.organization_name or t.event.organizer.username}</div>
                    
                    <div class="details">
                        <div>
                            <div class="label">Date & Time</div>
                            <div class="value">{t.event.start_date.strftime('%B %d, %Y - %I:%M %p')}</div>
                        </div>
                        <div>
                            <div class="label">Venue</div>
                            <div class="value">{t.event.venue}</div>
                        </div>
                        <div>
                            <div class="label">Attendee</div>
                            <div class="value">{t.billing_name}</div>
                        </div>
                        <div>
                            <div class="label">Ticket Type</div>
                            <div class="value">{t.ticket_type} (Qty: {t.quantity})</div>
                        </div>
                    </div>
                    
                    <div class="qr">
                        <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={t.ticket_number}" alt="QR Code">
                        <div style="font-size: 12px; color: #64748b; margin-top: 8px;">Scan at the entrance for check-in</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        response = HttpResponse(html_content, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="ticket_{t.ticket_number}.html"'
        return response
    except Ticket.DoesNotExist:
        return HttpResponse('Ticket not found', status=404)


from events.api_organizer_views import organizer_required

@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_bookings_list(request):
    """List bookings (tickets bought) for events organized by the logged-in user."""
    tickets = Ticket.objects.filter(event__organizer=request.user).select_related('event').order_by('-purchase_date')
    results = []
    for t in tickets:
        results.append({
            'ticket_number': t.ticket_number,
            'event_title': t.event.title,
            'event_id': t.event.id,
            'customer_name': t.billing_name,
            'customer_email': t.billing_email,
            'quantity': t.quantity,
            'price': float(t.price * t.quantity),
            'purchase_date': t.purchase_date.isoformat(),
            'status': t.status,
            'checked_in_at': t.checked_in_at.isoformat() if t.checked_in_at else None
        })
    return JsonResponse(results, safe=False)


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_tickets_list(request):
    """Same as bookings list for this schema."""
    return api_organizer_bookings_list(request)


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_tickets_stats(request, event_id=None):
    """Get ticket statistics (total, checked-in, recent)."""
    from django.db.models import Sum, Q
    tickets = Ticket.objects.filter(event__organizer=request.user)
    if event_id:
        tickets = tickets.filter(event_id=event_id)
        
    yesterday = timezone.now() - timezone.timedelta(days=1)
    
    stats = tickets.aggregate(
        total=Sum('quantity'),
        checked_in=Sum('quantity', filter=Q(status='checked_in')),
        recent=Sum('quantity', filter=Q(purchase_date__gte=yesterday))
    )
    
    total = stats['total'] or 0
    checked_in = stats['checked_in'] or 0
    recent = stats['recent'] or 0
    
    return JsonResponse({
        'total': total,
        'total_tickets': total,
        'checked_in': checked_in,
        'recent': recent,
        'recent_checkins': recent
    })


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_ticket_verify(request, ticket_number):
    """Verify a ticket for organizers."""
    try:
        t = Ticket.objects.select_related('event').get(ticket_number=ticket_number, event__organizer=request.user)
        is_valid = t.status == 'valid'
        msg = "Valid ticket"
        if t.status == 'checked_in':
            msg = "Ticket already checked in"
        elif t.status == 'cancelled':
            msg = "Ticket cancelled"
            
        return JsonResponse({
            'success': is_valid,
            'message': msg,
            'ticket': {
                'ticket_number': t.ticket_number,
                'event_title': t.event.title,
                'customer_name': t.billing_name,
                'status': t.status,
                'checked_in_at': t.checked_in_at.isoformat() if t.checked_in_at else None
            }
        })
    except Ticket.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Ticket not found or does not belong to your events.'}, status=404)


@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def api_organizer_ticket_checkin(request, ticket_number):
    """Mark a ticket as checked in."""
    try:
        t = Ticket.objects.select_related('event').get(ticket_number=ticket_number, event__organizer=request.user)
        if t.status == 'checked_in':
            return JsonResponse({'success': False, 'message': 'Ticket already checked in.'}, status=400)
        if t.status == 'cancelled':
            return JsonResponse({'success': False, 'message': 'Cannot check in a cancelled ticket.'}, status=400)
            
        t.status = 'checked_in'
        t.checked_in_at = timezone.now()
        t.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Check-in successful!',
            'ticket': {
                'ticket_number': t.ticket_number,
                'event_title': t.event.title,
                'customer_name': t.billing_name,
                'status': t.status,
                'checked_in_at': t.checked_in_at.isoformat()
            }
        })
    except Ticket.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Ticket not found or does not belong to your events.'}, status=404)


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_attendees_list(request):
    """List unique attendees who bought tickets to events organized by the user."""
    tickets = Ticket.objects.filter(event__organizer=request.user).select_related('event').order_by('-purchase_date')
    
    attendee_map = {}
    for t in tickets:
        email = t.billing_email.lower().strip()
        if email not in attendee_map:
            attendee_map[email] = {
                'name': t.billing_name,
                'email': t.billing_email,
                'phone': t.billing_phone,
                'purchased_event_ids': {t.event.id},
                'events_count': 1,
                'tickets_count': t.quantity,
                'total_spent': float(t.price * t.quantity),
                'last_purchase_date': t.purchase_date.isoformat()
            }
        else:
            attendee_map[email]['purchased_event_ids'].add(t.event.id)
            attendee_map[email]['events_count'] = len(attendee_map[email]['purchased_event_ids'])
            attendee_map[email]['tickets_count'] += t.quantity
            attendee_map[email]['total_spent'] += float(t.price * t.quantity)
            
    # Convert sets to lists for JSON serialization
    results = []
    for email, details in attendee_map.items():
        details['purchased_event_ids'] = list(details['purchased_event_ids'])
        results.append(details)
        
    return JsonResponse(results, safe=False)


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def api_organizer_attendees_stats(request):
    """Aggregate attendee statistics for organizer dashboard pages."""
    tickets = Ticket.objects.filter(event__organizer=request.user)
    total_attendees = tickets.values('billing_email').distinct().count()
    checked_in = tickets.filter(status='checked_in').values('billing_email').distinct().count()
    events_count = tickets.values('event_id').distinct().count()

    return JsonResponse({
        'total_attendees': total_attendees,
        'checked_in': checked_in,
        'events_count': events_count
    })


