import os
import json
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

STORE_FILE_PATH = os.path.join(settings.BASE_DIR, '.admin_data.json')

def load_store():
    if not os.path.exists(STORE_FILE_PATH):
        # Seed with initial mock data
        seed_data = seed_initial_data()
        save_store(seed_data)
        return seed_data
    try:
        with open(STORE_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading admin store: {e}")
        return seed_initial_data()

def save_store(data):
    try:
        with open(STORE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving admin store: {e}")

def seed_initial_data():
    User = get_user_model()
    # Find any actual attendees and organizers to make data link dynamically
    attendee = User.objects.filter(role='attendee').first()
    organizer = User.objects.filter(role='organizer').first()
    
    attendee_name = attendee.get_full_name() if attendee else "David Kamau"
    attendee_username = attendee.username if attendee else "davidk"
    attendee_email = attendee.email if attendee else "david.kamau@gmail.com"
    attendee_phone = getattr(attendee, 'phone', '0712345678') or "0712345678"
    
    organizer_name = organizer.get_full_name() or organizer.organization_name if organizer else "Yvonne Wambui"
    organizer_email = organizer.email if organizer else "yvonne@brightevents.co.ke"
    organizer_phone = getattr(organizer, 'phone', '0722345678') or "0722345678"

    now_iso = timezone.now().isoformat()
    two_hours_ago = (timezone.now() - timezone.timedelta(hours=2)).isoformat()
    yesterday = (timezone.now() - timezone.timedelta(days=1)).isoformat()

    support_tickets = [
        {
            "id": 1,
            "customer_name": attendee_name,
            "customer_email": attendee_email,
            "customer_phone": attendee_phone,
            "subject": "Unable to download ticket PDF",
            "message": "Hello, I recently booked a seat for the Music Festival but when I click download ticket, the PDF returns an error. Please assist.",
            "status": "open",
            "created_at": two_hours_ago,
            "replies": []
        },
        {
            "id": 2,
            "customer_name": organizer_name,
            "customer_email": organizer_email,
            "customer_phone": organizer_phone,
            "subject": "Payout processing timeline question",
            "message": "Hi Admin, my event 'Summer Music Fest' ended yesterday. When will the payout be processed to my bank account?",
            "status": "pending",
            "created_at": yesterday,
            "replies": [
                {
                    "sender": "admin",
                    "message": "Hello, payouts are processed within 2-3 business days after the event completes. We are reviewing your event sales now.",
                    "created_at": (timezone.now() - timezone.timedelta(hours=12)).isoformat()
                }
            ]
        },
        {
            "id": 3,
            "customer_name": "Alice Njeri",
            "customer_email": "alice.njeri@outlook.com",
            "customer_phone": "0733456789",
            "subject": "Change attendee details on booking",
            "message": "Hello, I bought two tickets but put the same name on both. Can I change one of them to my friend's name?",
            "status": "resolved",
            "created_at": (timezone.now() - timezone.timedelta(days=2)).isoformat(),
            "replies": [
                {
                    "sender": "admin",
                    "message": "Hello Alice, yes you can change details from your profile dashboard under tickets or let us know the name and we will update it for you.",
                    "created_at": (timezone.now() - timezone.timedelta(days=1)).isoformat()
                },
                {
                    "sender": "user",
                    "message": "Thank you, I was able to edit it from the profile page. Resolved!",
                    "created_at": (timezone.now() - timezone.timedelta(hours=18)).isoformat()
                }
            ]
        }
    ]

    return {
        "support_tickets": support_tickets,
        "next_support_ticket_id": 4,
        "approved_organizer_ids": [],
    }


def get_approved_organizer_ids():
    store = load_store()
    return store.get("approved_organizer_ids", [])


def approve_organizer(organizer_id):
    store = load_store()
    approved = store.get("approved_organizer_ids", [])
    organizer_id = int(organizer_id)
    if organizer_id not in approved:
        approved.append(organizer_id)
        store["approved_organizer_ids"] = approved
        save_store(store)
    return True


def _notification_state_map():
    try:
        from accounts.models import AdminNotificationState
        return {
            s.notification_key: s
            for s in AdminNotificationState.objects.all()
        }
    except Exception as e:
        print(f"Admin notification state unavailable: {e}")
        return {}


def _upsert_notification_state(notification_key, **fields):
    try:
        from accounts.models import AdminNotificationState
    except Exception as e:
        print(f"Admin notification state unavailable: {e}")
        return None
    state, _ = AdminNotificationState.objects.get_or_create(
        notification_key=notification_key,
        defaults=fields,
    )
    changed = False
    for key, value in fields.items():
        if getattr(state, key) != value:
            setattr(state, key, value)
            changed = True
    if changed:
        state.save(update_fields=[*fields.keys(), 'updated_at'])
    return state


def build_dynamic_notifications():
    """Build live notifications from current database state."""
    from events.models import Event
    from bookings.models import Ticket

    notifications = []

    pending_events = (
        Event.objects.filter(status='pending')
        .select_related('organizer', 'category')
        .order_by('-updated_at', '-created_at')[:25]
    )
    for event in pending_events:
        organizer_name = (
            event.organizer.organization_name
            or event.organizer.get_full_name()
            or event.organizer.username
        )
        timestamp = event.updated_at or event.created_at
        notifications.append({
            "id": f"event-pending-{event.id}",
            "title": "Event Pending Approval",
            "message": f"\"{event.title}\" submitted by {organizer_name} requires your approval.",
            "type": "warning",
            "is_read": False,
            "created_at": timestamp.isoformat(),
            "redirect_url": f"/admin-portal/events/detail/?id={event.id}",
            "entity_type": "event",
            "entity_id": event.id,
            "action_type": "event_pending_approval",
            "requires_action": True,
        })

    pending_refunds = (
        Ticket.objects.filter(status='cancelled')
        .select_related('event')
        .order_by('-purchase_date')[:25]
    )
    for ticket in pending_refunds:
        notifications.append({
            "id": f"refund-pending-{ticket.id}",
            "title": "Refund Request Pending",
            "message": (
                f"{ticket.billing_name or 'Customer'} requested a refund of "
                f"Kes {float(ticket.price * ticket.quantity):,.0f} for {ticket.event.title} "
                f"(booking {ticket.ticket_number})."
            ),
            "type": "info",
            "is_read": False,
            "created_at": ticket.purchase_date.isoformat(),
            "redirect_url": "/admin-portal/bookings/refunds/",
            "entity_type": "refund",
            "entity_id": ticket.id,
            "action_type": "refund_pending",
            "requires_action": True,
        })

    notifications.sort(key=lambda item: item["created_at"], reverse=True)
    return notifications


def get_notifications():
    """Return current actionable admin notifications, excluding dismissed items."""
    state_map = _notification_state_map()
    visible = []

    for notification in build_dynamic_notifications():
        state = state_map.get(notification["id"])
        if state and state.is_dismissed:
            continue
        if state:
            notification["is_read"] = state.is_read
        visible.append(notification)

    return visible


def _normalize_notification_key(notification_id):
    return str(notification_id)


def delete_notification(notification_id):
    return dismiss_notification(notification_id, force=True)


def dismiss_notification(notification_id, on_view=False, force=False):
    """Dismiss a notification. Actionable items auto-expire when the task is resolved."""
    key = _normalize_notification_key(notification_id)
    active_ids = {n["id"] for n in build_dynamic_notifications()}

    if key not in active_ids and not force:
        return False

    if on_view and not force:
        active = next((n for n in build_dynamic_notifications() if n["id"] == key), None)
        if active and active.get("requires_action"):
            return False

    _upsert_notification_state(key, is_dismissed=True, is_read=True)
    return True


def expire_notifications_for_entity(entity_type, entity_id, action_types=None):
    """Mark entity-linked notifications as dismissed after admin completes the action."""
    entity_id = str(entity_id)
    keys = []

    for notification in build_dynamic_notifications():
        if notification.get("entity_type") != entity_type:
            continue
        if str(notification.get("entity_id")) != entity_id:
            continue
        if action_types and notification.get("action_type") not in action_types:
            continue
        keys.append(notification["id"])

    if entity_type == "event":
        keys.append(f"event-pending-{entity_id}")
    elif entity_type == "refund":
        keys.append(f"refund-pending-{entity_id}")

    for key in set(keys):
        _upsert_notification_state(key, is_dismissed=True, is_read=True)
    return True


def mark_notification_read(notification_id):
    key = _normalize_notification_key(notification_id)
    _upsert_notification_state(key, is_read=True)
    return True


def mark_all_notifications_read():
    for notification in get_notifications():
        _upsert_notification_state(notification["id"], is_read=True)
    return True


def add_notification(*args, **kwargs):
    """Legacy hook — notifications are generated dynamically from database state."""
    return None

def get_support_tickets():
    store = load_store()
    return store.get("support_tickets", [])

def get_support_ticket_detail(ticket_id):
    tickets = get_support_tickets()
    for t in tickets:
        if t["id"] == int(ticket_id):
            return t
    return None

def add_support_ticket_reply(ticket_id, sender, message):
    store = load_store()
    tickets = store.get("support_tickets", [])
    for t in tickets:
        if t["id"] == int(ticket_id):
            t["replies"].append({
                "sender": sender,
                "message": message,
                "created_at": timezone.now().isoformat()
            })
            if sender == 'admin':
                t["status"] = 'pending'
            break
    store["support_tickets"] = tickets
    save_store(store)
    return True

def update_support_ticket_status(ticket_id, status):
    store = load_store()
    tickets = store.get("support_tickets", [])
    for t in tickets:
        if t["id"] == int(ticket_id):
            t["status"] = status
            break
    store["support_tickets"] = tickets
    save_store(store)
    return True
