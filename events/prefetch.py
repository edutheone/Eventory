"""
Async cache warming for the public events catalog.

Runs in a background thread after login so the first visit to /events/
hits a warm Django cache instead of waiting on a cold database query.
"""
import logging
import threading

logger = logging.getLogger(__name__)


def warm_events_catalog_cache():
    """Populate Django cache for the default attendee events catalog and categories."""
    try:
        from django.test import RequestFactory

        from events.views import api_category_list, api_event_list

        factory = RequestFactory()
        events_request = factory.get('/api/attendee/events/', {'limit': '200', 'page': '1'})
        api_event_list(events_request)

        categories_request = factory.get('/api/attendee/categories/')
        api_category_list(categories_request)

        logger.info('Events catalog cache warmed successfully')
    except Exception as exc:
        logger.warning('Events catalog cache warm failed: %s', exc)


def schedule_events_catalog_warm():
    """Fire-and-forget cache warm — does not block the login response."""
    thread = threading.Thread(target=warm_events_catalog_cache, daemon=True)
    thread.start()
