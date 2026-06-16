import logging
import traceback
from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import render

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        # Log the exception with full traceback
        logger.error(
            "Unhandled exception processing request for %s: %s",
            request.path,
            exception,
            exc_info=True
        )

        is_api = request.path.startswith('/api/') or request.headers.get('x-requested-with') == 'XMLHttpRequest'

        if is_api:
            # Prepare standard generic error response
            response_data = {
                'error': 'Something went wrong. Please try again later.'
            }

            # If user is admin, provide technical details
            if hasattr(request, 'user') and request.user.is_authenticated and getattr(request.user, 'role', '') == 'admin':
                response_data['admin_details'] = traceback.format_exc()

            return JsonResponse(response_data, status=500)
        else:
            # Let Django's default HTML error handler take over if DEBUG is False
            # Or we could render a custom error page here
            pass

        return None
