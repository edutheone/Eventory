from django.urls import path

from . import views
from . import google_auth


urlpatterns = [
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/google/', google_auth.google_oauth_callback, name='google_oauth'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/refresh-token/', views.refresh_token, name='refresh_token'),
    path('auth/check-status/', views.check_status, name='check_status'),
    path('auth/change-password/', views.change_password, name='change_password'),
    path('profile/', views.profile_detail, name='profile_detail'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('profile/stats/', views.profile_stats, name='profile_stats'),
    path('profile/upload-avatar/', views.profile_upload_avatar, name='profile_upload_avatar'),
    path('profile/delete-account/', views.profile_delete_account, name='profile_delete_account'),
]
