import hashlib
import json
import logging
import os
import secrets
from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model
from django.db import DatabaseError
from django.http import JsonResponse
from django.utils import timezone

from .models import APIToken

logger = logging.getLogger(__name__)


ACCESS_TOKEN_LIFETIME = timedelta(minutes=30)
REFRESH_TOKEN_LIFETIME = timedelta(days=7)


def parse_json_body(request):
    if not request.body:
        return {}

    try:
        return json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def json_error(message, status=400, errors=None):
    payload = {'error': message, 'message': message}
    if errors:
        payload['errors'] = errors
    return JsonResponse(payload, status=status)


def database_unavailable_response(exc):
    logger.exception('Database error during authentication: %s', exc)
    return json_error(
        'The authentication database is not ready. '
        'An administrator should open /api/events/run-migrations/ to initialize '
        'the Supabase schema, then try signing in again.',
        status=503,
        errors={'detail': str(exc)},
    )


def retry_after_migration_repair(request, view_callable):
    """On managed Postgres (Supabase), repair migration history once and retry."""
    if not os.environ.get('DATABASE_URL'):
        return None
    if getattr(request, '_db_repair_attempted', False):
        return None
    request._db_repair_attempted = True
    try:
        from config.db_migrations import run_migrations
        if run_migrations().get('success'):
            return view_callable(request)
    except Exception:
        logger.exception('Migration repair during auth failed')
    return None


def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_token(user, token_type, lifetime):
    raw_token = secrets.token_urlsafe(48)
    APIToken.objects.create(
        user=user,
        token_hash=token_hash(raw_token),
        token_type=token_type,
        expires_at=timezone.now() + lifetime,
    )
    return raw_token


def issue_token_pair(user):
    return {
        'access': create_token(user, 'access', ACCESS_TOKEN_LIFETIME),
        'refresh': create_token(user, 'refresh', REFRESH_TOKEN_LIFETIME),
        'token_type': 'Bearer',
        'expires_in': int(ACCESS_TOKEN_LIFETIME.total_seconds()),
    }


def get_bearer_token(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    return auth_header.split(' ', 1)[1].strip()


def authenticate_bearer(request, required_roles=None):
    raw_token = get_bearer_token(request)
    if not raw_token:
        return None, json_error('Authentication credentials were not provided.', status=401)

    token = (
        APIToken.objects.select_related('user')
        .filter(token_hash=token_hash(raw_token), token_type='access')
        .first()
    )
    if not token or not token.is_active or not token.user.is_active:
        return None, json_error('Invalid or expired token.', status=401)

    if required_roles and token.user.role not in required_roles and not token.user.is_superuser:
        return None, json_error('You do not have permission to perform this action.', status=403)

    return token.user, None


def revoke_user_tokens(user, refresh_token=None):
    tokens = APIToken.objects.filter(user=user, revoked_at__isnull=True)
    if refresh_token:
        tokens = tokens.filter(token_hash=token_hash(refresh_token), token_type='refresh')
    tokens.update(revoked_at=timezone.now())


def login_user(identifier, password):
    User = get_user_model()
    username = identifier

    if identifier and '@' in identifier:
        user = User.objects.filter(email__iexact=identifier).first()
        username = user.username if user else identifier

    return authenticate(username=username, password=password)
