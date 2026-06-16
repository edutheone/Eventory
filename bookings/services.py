from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from events.models import Event
from .models import Ticket
from .email_service import send_ticket_confirmation


class FulfillmentError(Exception):
    def __init__(self, message, code='fulfillment_error'):
        self.message = message
        self.code = code
        super().__init__(message)


def compute_tier_price(event, ticket_type):
    ticket_type = (ticket_type or 'Regular').strip()
    if ticket_type == 'VIP':
        if event.vip_price is None:
            raise FulfillmentError('VIP tickets are not available for this event.', 'tier_unavailable')
        return Decimal(str(event.vip_price))
    if ticket_type == 'VVIP':
        if event.vvip_price is None:
            raise FulfillmentError('VVIP tickets are not available for this event.', 'tier_unavailable')
        return Decimal(str(event.vvip_price))
    return Decimal(str(event.price))


def compute_order_total(event, ticket_type, quantity):
    unit_price = compute_tier_price(event, ticket_type)
    qty = max(1, int(quantity))
    return unit_price, qty, unit_price * qty


@transaction.atomic
def fulfill_payment_order(order):
    from payments.models import PaymentOrder

    # Do not select_related('ticket') here — nullable FK + select_for_update()
    # causes Postgres error: "FOR UPDATE cannot be applied to the nullable side
    # of an outer join".
    order = PaymentOrder.objects.select_for_update().select_related(
        'attendee', 'event', 'organizer'
    ).get(pk=order.pk)

    if order.ticket_id:
        raise FulfillmentError('This order has already been fulfilled.', 'already_fulfilled')

    fulfillable_statuses = ('pending_payment', 'failed', 'manual_review', 'verifying')
    if order.status not in fulfillable_statuses:
        # Allow repair when an order was marked completed without issuing a ticket.
        if not (order.status == 'completed' and not order.ticket_id):
            raise FulfillmentError('Order cannot be fulfilled in its current state.', 'invalid_status')

    event = Event.objects.select_for_update().get(pk=order.event_id)

    if event.status != 'published':
        raise FulfillmentError('This event is not available for booking.', 'event_unavailable')

    if event.end_date < timezone.now():
        raise FulfillmentError('This event has already ended.', 'event_ended')

    if event.available_seats < order.quantity:
        raise FulfillmentError('Not enough tickets available.', 'sold_out')

    unit_price = compute_tier_price(event, order.ticket_type)
    attendee = order.attendee
    billing_name = attendee.get_full_name() or attendee.username
    billing_email = (attendee.email or '').strip()
    if not billing_email:
        billing_email = f'{attendee.username}@users.eventhub.local'
    billing_phone = getattr(attendee, 'phone', '') or ''

    ticket = Ticket.objects.create(
        attendee=attendee,
        event=event,
        ticket_type=order.ticket_type,
        quantity=order.quantity,
        price=unit_price,
        billing_name=billing_name,
        billing_email=billing_email,
        billing_phone=billing_phone,
        status='valid',
    )

    event.available_seats = max(0, event.available_seats - order.quantity)
    if event.available_seats == 0:
        event.status = 'sold_out'
    event.save(update_fields=['available_seats', 'status', 'updated_at'])

    order.ticket = ticket
    order.status = 'completed'
    order.verification_message = 'Payment verified and ticket issued.'
    order.save(update_fields=['ticket', 'status', 'verification_message', 'updated_at'])

    send_ticket_confirmation(
        user_email=billing_email,
        user_name=billing_name,
        event_title=event.title,
        ticket_quantity=order.quantity,
        total_price=float(order.total_amount),
    )

    return ticket
