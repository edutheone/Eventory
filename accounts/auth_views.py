import json
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import User as CustomUser

@csrf_exempt
@require_http_methods(["POST"])
def login_submit(request):
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')
        
        if not email or not password:
            return JsonResponse({'success': False, 'error': 'Email and password required'}, status=400)
        
        user = authenticate(request, username=email, password=password)
        
        if user is None:
            return JsonResponse({'success': False, 'error': 'Invalid credentials'}, status=401)
        
        # Check role
        if role == 'organizer' and user.role != 'organizer':
            return JsonResponse({'success': False, 'error': 'Not an organizer account'}, status=403)
        
        login(request, user)
        
        if user.role == 'admin' or user.is_staff or user.is_superuser:
            redirect_url = '/admin-portal/dashboard/'
        else:
            redirect_url = '/attendee/dashboard/' if role != 'organizer' else '/organizer/dashboard/'
        
        return JsonResponse({
            'success': True,
            'redirect_url': redirect_url,
            'user': {
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'role': user.role
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def register_submit(request):
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        name = data.get('name')
        email = data.get('email')
        password = data.get('password1')
        role = data.get('role')
        organization_name = data.get('organization_name')
        
        if not name or not email or not password:
            return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
        
        if CustomUser.objects.filter(username=email).exists():
            return JsonResponse({'success': False, 'error': 'Email already registered'}, status=400)
        
        # Create user
        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='attendee'
        )
        
        login(request, user)
        
        redirect_url = '/attendee/dashboard/'
        
        return JsonResponse({
            'success': True,
            'redirect_url': redirect_url,
            'user': {
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'role': user.role
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
