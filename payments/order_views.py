import json
import logging
import time
from io import BytesIO

from django.db.utils import ProgrammingError
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from accounts.auth import authenticate_bearer, parse_json_body
from bookings.services import compute_order_total, fulfill_payment_order, FulfillmentError
from events.api_organizer_views import organizer_required
from events.models import Event

from .models import PaymentOrder, OrganizerNotification, AttendeeNotification
from .mpesa import MpesaClient
from .screenshot_verifier import verify_screenshot as analyze_payment_screenshot
from .screenshot_storage import encode_upload_to_data_uri, open_screenshot_stream, order_has_screenshot

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
MAX_SCREENSHOT_SIZE = 5 * 1024 * 1024


def get_authenticated_user(request):
    user = request.user
    if not user.is_authenticated:
        bearer_user, _ = authenticate_bearer(request)
        if bearer_user:
            user = bearer_user
    return user if user.is_authenticated else None


def _sse_event(step, message, **extra):
    payload = {'step': step, 'message': message, **extra}
    return f"data: {json.dumps(payload)}\n\n"


def _organizer_numbers(organizer):
    return [
        organizer.mpesa_paybill,
        organizer.mpesa_till,
        organizer.mpesa_pochi,
        organizer.mpesa_send_money,
    ]


def _serialize_order(order, include_payment=False):
    data = {
        'id': order.id,
        'event_id': order.event_id,
        'event_title': order.event.title,
        'ticket_type': order.ticket_type,
        'quantity': order.quantity,
        'unit_price': float(order.unit_price),
        'total_amount': float(order.total_amount),
        'status': order.status,
        'verification_message': order.verification_message,
        'submitted_mpesa_name': order.submitted_mpesa_name,
        'screenshot_verified': order.screenshot_verified,
        'ticket_number': order.ticket.ticket_number if order.ticket_id else None,
        'payment_rail': order.payment_rail,
        'stk_status': order.stk_status,
        'mpesa_receipt': order.mpesa_receipt,
        'created_at': order.created_at.isoformat(),
        'updated_at': order.updated_at.isoformat(),
    }
    if include_payment:
        organizer = order.organizer
        data['mpesa_display_name'] = organizer.mpesa_display_name
        data['payment_options'] = organizer.mpesa_payment_options()
        data['stk_available'] = MpesaClient.is_configured()
    return data


def _notify_organizer_payment_review(order, *, ocr_passed):
    """Step 2: always notify organizer to approve and issue the ticket."""
    attendee = order.attendee
    attendee_name = attendee.get_full_name() or attendee.username
    if ocr_passed:
        title = 'Payment ready to approve (auto-verified)'
        message = (
            f'{attendee_name} — M-Pesa screenshot auto-verified for '
            f'{order.event.title} ({order.ticket_type}, KES {order.total_amount}). '
            f'Approve to issue the ticket.'
        )
        notification_type = 'success'
    else:
        title = 'Payment approval needed'
        message = (
            f'{attendee_name} — screenshot could not be auto-verified for '
            f'{order.event.title} ({order.ticket_type}, KES {order.total_amount}). '
            f'Review the screenshot and approve to issue the ticket.'
        )
        notification_type = 'warning'

    OrganizerNotification.objects.create(
        organizer=order.organizer,
        payment_order=order,
        title=title,
        message=message,
        notification_type=notification_type,
        requires_action=True,
        action_type='payment_approval',
    )


def _notify_attendee_payment_review(order, *, ocr_passed):
    if ocr_passed:
        message = (
            f'Your payment for {order.event.title} was verified automatically. '
            f'The organizer will confirm and issue your ticket shortly.'
        )
    else:
        message = (
            f'Your payment for {order.event.title} has been sent to the organizer for review. '
            f'You will be notified when your ticket is issued.'
        )
    AttendeeNotification.objects.create(
        attendee=order.attendee,
        payment_order=order,
        title='Payment submitted for review',
        message=message,
        notification_type='info',
    )


def _escalate_to_organizer_review(order, *, ocr_passed, verification_message, mpesa_name=''):
    """Route order to organizer approval (step 2). Tickets are issued only on approve."""
    order.status = 'manual_review'
    order.screenshot_verified = ocr_passed
    order.verification_message = verification_message or (
        'Screenshot auto-verified. Awaiting organizer approval.'
        if ocr_passed
        else 'Screenshot could not be auto-verified. Awaiting organizer approval.'
    )
    if mpesa_name:
        order.submitted_mpesa_name = mpesa_name
    order.save(
        update_fields=[
            'status',
            'screenshot_verified',
            'verification_message',
            'submitted_mpesa_name',
            'updated_at',
        ]
    )
    _notify_organizer_payment_review(order, ocr_passed=ocr_passed)
    _notify_attendee_payment_review(order, ocr_passed=ocr_passed)


@csrf_exempt
@require_http_methods(["POST"])
def create_payment_order(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login to purchase tickets.'}, status=401)

    data = parse_json_body(request)
    if data is None:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body.'}, status=400)

    event_id = data.get('event_id')
    ticket_type = data.get('ticket_type', 'Regular')
    quantity = data.get('quantity', 1)

    try:
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Quantity must be at least 1.'}, status=400)

    try:
        event = Event.objects.select_related('organizer').get(pk=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found.'}, status=404)

    if event.status != 'published':
        return JsonResponse({'success': False, 'message': 'This event is not available for booking.'}, status=400)

    if event.end_date < timezone.now():
        return JsonResponse({'success': False, 'message': 'This event has already ended.'}, status=400)

    if event.available_seats < quantity:
        return JsonResponse({'success': False, 'message': 'Not enough tickets available.'}, status=400)

    organizer = event.organizer
    stk_available = MpesaClient.is_configured()
    if not organizer.has_mpesa_payment_config() and not stk_available:
        return JsonResponse({
            'success': False,
            'message': 'Organizer has not configured M-Pesa payment details yet.',
        }, status=400)

    try:
        unit_price, qty, total_amount = compute_order_total(event, ticket_type, quantity)
    except FulfillmentError as exc:
        return JsonResponse({'success': False, 'message': exc.message}, status=400)

    order_fields = {
        'attendee': user,
        'event': event,
        'organizer': organizer,
        'ticket_type': ticket_type,
        'quantity': qty,
        'unit_price': unit_price,
        'total_amount': total_amount,
        'status': 'pending_payment',
    }
    try:
        order = PaymentOrder.objects.create(**order_fields)
    except ProgrammingError as exc:
        if 'payments_paymentorder' not in str(exc).lower():
            raise
        from config.db_migrations import run_migrations
        migration_result = run_migrations()
        if not migration_result.get('success'):
            return JsonResponse({
                'success': False,
                'message': 'Payment system is being updated. Please try again in a moment.',
            }, status=503)
        order = PaymentOrder.objects.create(**order_fields)

    return JsonResponse({
        'success': True,
        'order': _serialize_order(order, include_payment=True),
    })


@csrf_exempt
@require_http_methods(["GET"])
def payment_order_status(request, order_id):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    try:
        order = PaymentOrder.objects.select_related('event', 'organizer', 'ticket').get(pk=order_id, attendee=user)
    except PaymentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found.'}, status=404)

    return JsonResponse({'success': True, 'order': _serialize_order(order, include_payment=True)})


@csrf_exempt
@require_http_methods(["POST"])
def verify_screenshot(request, order_id):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    try:
        order = PaymentOrder.objects.select_related('event', 'organizer', 'ticket').get(pk=order_id, attendee=user)
    except PaymentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found.'}, status=404)

    if order.status not in ('pending_payment', 'failed', 'rejected'):
        return JsonResponse({'success': False, 'message': 'This order cannot accept a new screenshot.'}, status=400)

    screenshot = request.FILES.get('screenshot')
    if not screenshot:
        return JsonResponse({'success': False, 'message': 'Screenshot file is required.'}, status=400)

    if screenshot.size > MAX_SCREENSHOT_SIZE:
        return JsonResponse({'success': False, 'message': 'Screenshot must be 5 MB or smaller.'}, status=400)

    content_type = getattr(screenshot, 'content_type', '') or ''
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({'success': False, 'message': 'Only JPEG, PNG, or WebP images are allowed.'}, status=400)

    try:
        data_uri, screenshot_bytes = encode_upload_to_data_uri(screenshot, content_type=content_type)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'Could not read screenshot: {exc}'}, status=400)

    order.status = 'verifying'
    order.screenshot_data = data_uri
    order.verification_message = ''
    order.save(update_fields=['status', 'screenshot_data', 'verification_message', 'updated_at'])

    def event_stream():
        yield _sse_event('upload_received', 'Screenshot received')
        time.sleep(0.2)
        yield _sse_event('preprocessing', 'Preparing image for analysis')
        time.sleep(0.2)
        yield _sse_event('reading_text', 'Reading transaction details')

        image_stream = open_screenshot_stream(order)
        if image_stream is None:
            image_stream = BytesIO(screenshot_bytes)

        try:
            result = analyze_payment_screenshot(
                image_stream,
                order.organizer.mpesa_display_name,
                order.total_amount,
                _organizer_numbers(order.organizer),
            )
        except Exception as exc:
            order.ocr_raw_text = ''
            order.save(update_fields=['ocr_raw_text', 'updated_at'])
            _escalate_to_organizer_review(
                order,
                ocr_passed=False,
                verification_message=f'Automatic verification error: {exc}',
            )
            yield _sse_event(
                'pending_approval',
                'Your payment has been sent to the organizer for approval.',
                ocr_passed=False,
                order_id=order.id,
            )
            return

        order.ocr_raw_text = result.get('ocr_text', '')
        order.save(update_fields=['ocr_raw_text', 'updated_at'])

        yield _sse_event('checking_amount', 'Verifying payment amount')
        time.sleep(0.2)
        yield _sse_event('checking_recipient', 'Verifying recipient name')

        ocr_passed = bool(result.get('success'))
        _escalate_to_organizer_review(
            order,
            ocr_passed=ocr_passed,
            verification_message=result.get('notes', ''),
        )
        order.refresh_from_db()

        if ocr_passed:
            message = (
                'Screenshot verified! Your payment has been sent to the organizer '
                'for final approval.'
            )
        else:
            message = (
                'We could not fully verify your screenshot automatically, but your '
                'payment has been sent to the organizer for approval.'
            )

        yield _sse_event(
            'pending_approval',
            message,
            ocr_passed=ocr_passed,
            order_id=order.id,
        )

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
@require_http_methods(["POST"])
def payment_order_stk_push(request, order_id):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    if not MpesaClient.is_configured():
        return JsonResponse({
            'success': False,
            'message': 'M-Pesa STK Push is not available right now. Please pay manually.',
        }, status=503)

    data = parse_json_body(request)
    if data is None:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body.'}, status=400)

    phone = (data.get('phone') or data.get('phone_number') or '').strip()
    if not phone:
        return JsonResponse({'success': False, 'message': 'M-Pesa phone number is required.'}, status=400)

    normalized_phone = MpesaClient.normalize_phone(phone)
    if not normalized_phone.startswith('254') or len(normalized_phone) != 12:
        return JsonResponse({
            'success': False,
            'message': 'Enter a valid Kenyan M-Pesa number (e.g. 0712345678).',
        }, status=400)

    try:
        order = PaymentOrder.objects.select_related('event').get(pk=order_id, attendee=user)
    except PaymentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found.'}, status=404)

    if order.status == 'completed':
        return JsonResponse({
            'success': True,
            'message': 'Payment already completed.',
            'order': _serialize_order(order),
        })

    if order.status not in ('pending_payment', 'failed', 'rejected'):
        return JsonResponse({
            'success': False,
            'message': 'This order cannot start a new M-Pesa prompt.',
        }, status=400)

    client = MpesaClient()
    account_ref = f'ORD{order.id}'
    description = (order.event.title or 'EventHub')[:13]

    try:
        result = client.stk_push(
            phone_number=normalized_phone,
            amount=order.total_amount,
            account_ref=account_ref,
            description=description,
        )
    except Exception as exc:
        logger.exception('STK push failed for order %s', order.id)
        return JsonResponse({
            'success': False,
            'message': f'Could not send M-Pesa prompt: {exc}',
        }, status=502)

    if str(result.get('ResponseCode')) != '0':
        message = (
            result.get('errorMessage')
            or result.get('ResponseDescription')
            or result.get('error')
            or 'M-Pesa could not send the payment prompt.'
        )
        return JsonResponse({'success': False, 'message': message}, status=400)

    order.payment_rail = 'stk_platform'
    order.payer_phone = normalized_phone
    order.checkout_request_id = result.get('CheckoutRequestID', '')
    order.merchant_request_id = result.get('MerchantRequestID', '')
    order.stk_status = 'initiated'
    order.status = 'verifying'
    order.verification_message = 'Waiting for M-Pesa confirmation on your phone.'
    order.save(update_fields=[
        'payment_rail',
        'payer_phone',
        'checkout_request_id',
        'merchant_request_id',
        'stk_status',
        'status',
        'verification_message',
        'updated_at',
    ])

    return JsonResponse({
        'success': True,
        'message': 'Check your phone for the M-Pesa prompt and enter your PIN.',
        'checkout_request_id': order.checkout_request_id,
        'order': _serialize_order(order),
    })


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_stk_callback(request):
    """Daraja STK callback — auto-fulfills PaymentOrder on success."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        stk_callback = data['Body']['stkCallback']
        checkout_id = stk_callback['CheckoutRequestID']
        result_code = stk_callback['ResultCode']
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning('Invalid M-Pesa callback payload: %s', exc)
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    try:
        order = PaymentOrder.objects.select_related('event', 'organizer', 'attendee').get(
            checkout_request_id=checkout_id,
        )
    except PaymentOrder.DoesNotExist:
        logger.warning('M-Pesa callback for unknown CheckoutRequestID: %s', checkout_id)
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    if order.status == 'completed' and order.ticket_id:
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    if result_code == 0:
        meta = {}
        callback_metadata = stk_callback.get('CallbackMetadata') or {}
        for item in callback_metadata.get('Item', []):
            meta[item.get('Name')] = item.get('Value')

        order.mpesa_receipt = str(meta.get('MpesaReceiptNumber', '') or '')
        order.stk_status = 'success'
        order.verification_message = 'M-Pesa payment confirmed.'
        order.save(update_fields=[
            'mpesa_receipt',
            'stk_status',
            'verification_message',
            'updated_at',
        ])

        try:
            ticket = fulfill_payment_order(order)
        except FulfillmentError as exc:
            logger.error('STK fulfillment failed for order %s: %s', order.id, exc.message)
            order.status = 'failed'
            order.stk_status = 'failed'
            order.verification_message = exc.message
            order.save(update_fields=['status', 'stk_status', 'verification_message', 'updated_at'])
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        order.refresh_from_db()
        AttendeeNotification.objects.create(
            attendee=order.attendee,
            payment_order=order,
            title='Payment confirmed',
            message=(
                f'Your M-Pesa payment for {order.event.title} was successful. '
                f'Ticket {ticket.ticket_number} has been issued.'
            ),
            notification_type='success',
        )
    else:
        desc = stk_callback.get('ResultDesc', 'M-Pesa payment was not completed.')
        order.status = 'failed'
        order.stk_status = 'failed'
        order.verification_message = desc
        order.save(update_fields=['status', 'stk_status', 'verification_message', 'updated_at'])

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_http_methods(["POST"])
def submit_mpesa_name(request, order_id):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    data = parse_json_body(request)
    if data is None:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body.'}, status=400)

    mpesa_name = (data.get('mpesa_name') or '').strip()
    if len(mpesa_name) < 2:
        return JsonResponse({'success': False, 'message': 'Please enter your M-Pesa name.'}, status=400)

    try:
        order = PaymentOrder.objects.select_related('event', 'organizer', 'attendee').get(pk=order_id, attendee=user)
    except PaymentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found.'}, status=404)

    if order.status == 'manual_review':
        order.submitted_mpesa_name = mpesa_name
        order.save(update_fields=['submitted_mpesa_name', 'updated_at'])
        return JsonResponse({
            'success': True,
            'message': 'M-Pesa name updated for organizer review.',
            'order': _serialize_order(order),
        })

    if order.status not in ('failed', 'rejected', 'pending_payment'):
        return JsonResponse({'success': False, 'message': 'This order cannot be submitted for manual review.'}, status=400)

    _escalate_to_organizer_review(
        order,
        ocr_passed=False,
        verification_message='Submitted with M-Pesa name for organizer approval.',
        mpesa_name=mpesa_name,
    )

    return JsonResponse({
        'success': True,
        'message': 'Submitted for organizer approval.',
        'order': _serialize_order(order),
    })


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def organizer_pending_orders(request):
    orders = PaymentOrder.objects.filter(
        organizer=request.user,
        status='manual_review',
    ).select_related('attendee', 'event').order_by('-updated_at')

    results = []
    for order in orders:
        attendee = order.attendee
        results.append({
            'id': order.id,
            'event_id': order.event_id,
            'event_title': order.event.title,
            'ticket_type': order.ticket_type,
            'quantity': order.quantity,
            'total_amount': float(order.total_amount),
            'submitted_mpesa_name': order.submitted_mpesa_name,
            'screenshot_verified': order.screenshot_verified,
            'verification_message': order.verification_message,
            'has_screenshot': order_has_screenshot(order),
            'attendee_name': attendee.get_full_name() or attendee.username,
            'attendee_email': attendee.email,
            'status': order.status,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat(),
        })

    return JsonResponse({'success': True, 'orders': results})


@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def organizer_approve_order(request, order_id):
    try:
        order = PaymentOrder.objects.select_related('event', 'organizer', 'attendee').get(
            pk=order_id, organizer=request.user
        )
    except PaymentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found.'}, status=404)

    if order.status != 'manual_review':
        return JsonResponse({'success': False, 'message': 'Order is not awaiting approval.'}, status=400)

    try:
        ticket = fulfill_payment_order(order)
    except FulfillmentError as exc:
        return JsonResponse({'success': False, 'message': exc.message}, status=400)

    order.refresh_from_db()

    OrganizerNotification.objects.filter(
        payment_order=order, organizer=request.user, requires_action=True
    ).update(is_read=True, requires_action=False)

    AttendeeNotification.objects.create(
        attendee=order.attendee,
        payment_order=order,
        title='Payment approved',
        message=(
            f'Your payment for {order.event.title} was approved. '
            f'Ticket {ticket.ticket_number} has been issued.'
        ),
        notification_type='success',
    )

    return JsonResponse({
        'success': True,
        'message': 'Payment approved and ticket issued.',
        'ticket_number': ticket.ticket_number,
        'order': _serialize_order(order),
    })


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def organizer_payment_order_screenshot(request, order_id):
    try:
        order = PaymentOrder.objects.get(pk=order_id, organizer=request.user)
    except PaymentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found.'}, status=404)

    if not order.screenshot_data:
        return JsonResponse({'success': False, 'message': 'No screenshot on file.'}, status=404)

    return JsonResponse({
        'success': True,
        'screenshot_data': order.screenshot_data,
        'order_id': order.id,
    })


@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def organizer_reject_order(request, order_id):
    try:
        order = PaymentOrder.objects.select_related('event', 'organizer', 'attendee').get(
            pk=order_id, organizer=request.user
        )
    except PaymentOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found.'}, status=404)

    if order.status != 'manual_review':
        return JsonResponse({'success': False, 'message': 'Order is not awaiting approval.'}, status=400)

    order.status = 'rejected'
    order.verification_message = 'Payment rejected by organizer. Please submit your M-Pesa screenshot again.'
    order.save(update_fields=['status', 'verification_message', 'updated_at'])

    OrganizerNotification.objects.filter(
        payment_order=order, organizer=request.user, requires_action=True
    ).update(is_read=True, requires_action=False)

    AttendeeNotification.objects.create(
        attendee=order.attendee,
        payment_order=order,
        title='Payment not confirmed',
        message='Payment could not be confirmed. Please submit your M-Pesa screenshot again.',
        notification_type='warning',
    )

    return JsonResponse({
        'success': True,
        'message': 'Payment rejected.',
        'order': _serialize_order(order),
    })


def _serialize_organizer_notification(notification):
    return {
        'id': notification.id,
        'title': notification.title,
        'message': notification.message,
        'notification_type': notification.notification_type,
        'is_read': notification.is_read,
        'requires_action': notification.requires_action,
        'action_type': notification.action_type,
        'payment_order_id': notification.payment_order_id,
        'created_at': notification.created_at.isoformat(),
    }


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def organizer_notifications_list(request):
    notifications = OrganizerNotification.objects.filter(
        organizer=request.user,
    ).order_by('-created_at')[:50]
    results = [_serialize_organizer_notification(n) for n in notifications]
    return JsonResponse({'success': True, 'notifications': results})


@csrf_exempt
@organizer_required
@require_http_methods(["GET"])
def organizer_notifications_unread(request):
    count = OrganizerNotification.objects.filter(
        organizer=request.user, is_read=False,
    ).count()
    return JsonResponse({'success': True, 'unread_count': count})


@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def organizer_notification_mark_read(request, notification_id):
    updated = OrganizerNotification.objects.filter(
        pk=notification_id, organizer=request.user,
    ).update(is_read=True)
    if not updated:
        return JsonResponse({'success': False, 'message': 'Notification not found.'}, status=404)
    return JsonResponse({'success': True})


@csrf_exempt
@organizer_required
@require_http_methods(["POST"])
def organizer_notifications_mark_all_read(request):
    OrganizerNotification.objects.filter(
        organizer=request.user, is_read=False,
    ).update(is_read=True)
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(["GET"])
def attendee_notifications_list(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    notifications = AttendeeNotification.objects.filter(attendee=user).order_by('-created_at')[:50]
    results = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'notification_type': n.notification_type,
        'is_read': n.is_read,
        'payment_order_id': n.payment_order_id,
        'created_at': n.created_at.isoformat(),
    } for n in notifications]

    return JsonResponse({'success': True, 'notifications': results})


@csrf_exempt
@require_http_methods(["POST"])
def attendee_notification_mark_read(request, notification_id):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    updated = AttendeeNotification.objects.filter(pk=notification_id, attendee=user).update(is_read=True)
    if not updated:
        return JsonResponse({'success': False, 'message': 'Notification not found.'}, status=404)
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(["POST"])
def attendee_notifications_mark_all_read(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    AttendeeNotification.objects.filter(attendee=user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})
