from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth import get_user_model
import json
import random
from django.db import DatabaseError

from .auth import (
    database_unavailable_response,
    issue_token_pair,
    json_error,
    parse_json_body,
    retry_after_migration_repair,
)
from .views import user_payload

@csrf_exempt
@require_http_methods(['POST'])
def google_oauth_callback(request):
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
    except ImportError:
        return json_error('Google Authentication library is not installed on the server.', status=501)

    data = parse_json_body(request)
    if data is None:
        return json_error('Invalid JSON body.')
    
    credential = data.get('credential')
    role = data.get('role', 'attendee')
    
    if not credential:
        return json_error('Credential token is required.')
    
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None)
    if not client_id:
        return json_error('Google Client ID is not configured on the server.', status=500)
    
    try:
        # Verify the ID token
        idinfo = id_token.verify_oauth2_token(
            credential, 
            google_requests.Request(), 
            client_id
        )
        
        # ID token is valid. Get the user's Google Account ID, email, names
        email = idinfo.get('email')
        google_id = idinfo.get('sub')
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        picture = idinfo.get('picture', '')
        
        if not email:
            return json_error('Email not provided by Google.', status=400)
            
    except ValueError as e:
        return json_error(f'Invalid token: {str(e)}', status=400)
        
    User = get_user_model()

    try:
        return _complete_google_login(request, User, google_id, email, first_name, last_name, picture, role)
    except DatabaseError as exc:
        repaired = retry_after_migration_repair(request, google_oauth_callback)
        if repaired is not None:
            return repaired
        return database_unavailable_response(exc)


def _complete_google_login(request, User, google_id, email, first_name, last_name, picture, role):
    # 1. Try to find user by google_id or email
    user = User.objects.filter(google_id=google_id).first()
    if not user:
        user = User.objects.filter(email__iexact=email).first()
        if user:
            # Associate google_id with existing user
            user.google_id = google_id
            user.save(update_fields=['google_id'])
            
    # 2. If user doesn't exist, register them
    if not user:
        # Auto-generate a unique username
        email_prefix = email.split('@')[0]
        cleaned_prefix = "".join(c for c in email_prefix if c.isalnum() or c in ['.', '-', '_'])
        username = cleaned_prefix
        # Handle collision
        suffix_count = 0
        while User.objects.filter(username__iexact=username).exists():
            suffix_count += 1
            random_digits = str(random.randint(1000, 9999))
            username = f"{cleaned_prefix}_{random_digits}"
            if suffix_count > 10:
                username = f"{cleaned_prefix}_{random.randint(10000, 99999)}"
                
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='attendee',
            google_id=google_id,
            avatar_url=picture
        )
        user.set_unusable_password()
        user.save()
    else:
        update_fields = []
        if first_name and first_name != user.first_name:
            user.first_name = first_name
            update_fields.append('first_name')
        if last_name and last_name != user.last_name:
            user.last_name = last_name
            update_fields.append('last_name')
        if picture and user.avatar_url != picture:
            user.avatar_url = picture
            update_fields.append('avatar_url')
        if update_fields:
            user.save(update_fields=update_fields)
        
    # Check if active
    if not user.is_active:
        return json_error('This account is inactive.', status=403)
        
    # Standard role validation if logging in as organizer
    if role == 'organizer' and user.role != 'organizer' and not user.is_superuser:
        return json_error('Only organizer accounts can access the organizer portal.', status=403)
        
    # Generate token pair
    tokens = issue_token_pair(user)

    from events.prefetch import schedule_events_catalog_warm
    schedule_events_catalog_warm()
    
    return JsonResponse({
        'message': 'Login successful.',
        'user': user_payload(user),
        **tokens
    })
