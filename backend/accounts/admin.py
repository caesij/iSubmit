from django.contrib import admin
from .models import User, FacultyAccount, StaffAccount
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

@admin.register(FacultyAccount)
class FacultyAccountAdmin(BaseUserAdmin):
    list_display = ('first_name', 'middle_name', 'last_name', 'email', 'faculty_type', 'is_active')
    list_filter = ('faculty_type', 'is_active')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'middle_name', 'last_name')}),
        ('Faculty Info', {'fields': ('faculty_type',)}),
        ('Permissions', {'fields': ('is_active',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'middle_name', 'last_name', 'faculty_type', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.role = obj.Role.FACULTY
        super().save_model(request, obj, form, change)

@admin.register(StaffAccount)
class StaffAccountAdmin(BaseUserAdmin):
    list_display = ('first_name', 'middle_name', 'last_name', 'email', 'is_active')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'middle_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'middle_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        obj.role = obj.Role.STAFF
        super().save_model(request, obj, form, change)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('first_name', 'middle_name', 'last_name', 'email', 'role', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'middle_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'middle_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )