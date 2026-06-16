import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from bookings.models import Ticket
from bookings.views import get_authenticated_attendee
from events.models import Event

from .models import EventReview


def _review_payload(review):
    return {
        'id': review.id,
        'event_id': review.event_id,
        'event_title': review.event.title,
        'rating': review.rating,
        'comment': review.comment,
        'created_at': review.created_at.isoformat(),
        'updated_at': review.updated_at.isoformat(),
    }


def _user_can_review_event(user, event):
    """Attendee may review only past events they attended (valid ticket)."""
    if event.end_date >= timezone.now():
        return False, 'You can only review events that have ended.'
    ticket = Ticket.objects.filter(
        attendee=user,
        event=event,
        status__in=['valid', 'checked_in'],
    ).order_by('-purchase_date').first()
    if not ticket:
        return False, 'You need a ticket for this event to leave a review.'
    return True, None, ticket


@csrf_exempt
@require_http_methods(['GET'])
def api_my_reviews(request):
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    reviews = EventReview.objects.filter(user=user).select_related('event')
    results = [_review_payload(r) for r in reviews]
    return JsonResponse({'success': True, 'results': results, 'count': len(results)})


@csrf_exempt
@require_http_methods(['GET'])
def api_event_reviews(request, event_id):
    reviews = EventReview.objects.filter(event_id=event_id).select_related('user', 'event')
    results = []
    for review in reviews:
        name = (
            getattr(review.user, 'full_name', None)
            or review.user.get_full_name()
            or review.user.username
        )
        results.append({
            'id': review.id,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.isoformat(),
            'user_name': name,
        })
    avg = 0
    if results:
        avg = sum(r['rating'] for r in results) / len(results)
    return JsonResponse({
        'success': True,
        'results': results,
        'count': len(results),
        'average_rating': round(avg, 1),
    })


@csrf_exempt
@require_http_methods(['POST'])
def api_create_review(request, event_id):
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Event not found.'}, status=404)

    allowed, reason, ticket = _user_can_review_event(user, event)
    if not allowed:
        return JsonResponse({'success': False, 'message': reason}, status=403)

    if EventReview.objects.filter(user=user, event=event).exists():
        return JsonResponse({'success': False, 'message': 'You already reviewed this event.'}, status=400)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON.'}, status=400)

    rating = data.get('rating')
    comment = (data.get('comment') or '').strip()

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Rating must be between 1 and 5.'}, status=400)

    if rating < 1 or rating > 5:
        return JsonResponse({'success': False, 'message': 'Rating must be between 1 and 5.'}, status=400)

    review = EventReview.objects.create(
        user=user,
        event=event,
        ticket=ticket,
        rating=rating,
        comment=comment,
    )
    return JsonResponse({'success': True, 'review': _review_payload(review)}, status=201)


@csrf_exempt
@require_http_methods(['PUT', 'PATCH'])
def api_update_review(request, review_id):
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    try:
        review = EventReview.objects.select_related('event').get(pk=review_id, user=user)
    except EventReview.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Review not found.'}, status=404)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON.'}, status=400)

    if 'rating' in data:
        try:
            rating = int(data['rating'])
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Rating must be between 1 and 5.'}, status=400)
        if rating < 1 or rating > 5:
            return JsonResponse({'success': False, 'message': 'Rating must be between 1 and 5.'}, status=400)
        review.rating = rating

    if 'comment' in data:
        review.comment = (data['comment'] or '').strip()

    review.save()
    return JsonResponse({'success': True, 'review': _review_payload(review)})


@csrf_exempt
@require_http_methods(['DELETE'])
def api_delete_review(request, review_id):
    user = get_authenticated_attendee(request)
    if not user or not user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login.'}, status=401)

    deleted, _ = EventReview.objects.filter(pk=review_id, user=user).delete()
    if not deleted:
        return JsonResponse({'success': False, 'message': 'Review not found.'}, status=404)
    return JsonResponse({'success': True})
