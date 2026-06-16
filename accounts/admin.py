from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import APIToken, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('EventHub Profile', {'fields': ('role', 'phone', 'organization_name')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('EventHub Profile', {'fields': ('role', 'phone', 'organization_name')}),
    )
    list_display = ('username', 'email', 'role', 'organization_name', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'organization_name')


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_type', 'created_at', 'expires_at', 'revoked_at')
    list_filter = ('token_type', 'created_at', 'expires_at', 'revoked_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('token_hash', 'created_at')
