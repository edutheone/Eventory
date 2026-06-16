from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.urls import reverse

def admin_login_page(request):
    """Admin login page"""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('/admin-portal/dashboard/')
    return render(request, 'admin/login.html')

def admin_login_submit(request):
    """Process admin login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            # IMPORTANT: Use a different redirect - not back to login
            return redirect('/admin-portal/dashboard/')
        else:
            messages.error(request, 'Invalid credentials or you do not have admin access.')
            return redirect('/admin/login/')
    
    return redirect('/admin/login/')

def admin_logout_view(request):
    """Admin logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('/login/')
