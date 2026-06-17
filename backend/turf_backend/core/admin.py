from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
# pyrefly: ignore [missing-import]
from .models import Location, AppUser

@admin.register(AppUser)
class AppUserAdmin(UserAdmin):
    model = AppUser
    list_display = ('email', 'name', 'role', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('name', 'mobile', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'mobile', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )

admin.site.register(Location)