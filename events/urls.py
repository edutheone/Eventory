from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.home, name='home'),
    path('events', views.event_list, name='event_list_no_slash'),
    path('events/', views.event_list, name='event_list'),
    path('organizer/dashboard/', views.organizer_dashboard, name='organizer_dashboard'),
    path('api/organizer/dashboard/stats/', views.organizer_dashboard_stats, name='organizer_dashboard_stats'),
    path('api/organizer/dashboard/revenue/', views.organizer_dashboard_revenue, name='organizer_dashboard_revenue'),
    path('api/organizer/events/<int:event_id>/analytics/', views.api_organizer_event_analytics, name='api_organizer_event_analytics'),
]
