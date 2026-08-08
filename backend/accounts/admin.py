from django.contrib import admin
from .models import User, FacultyAccount, StaffAccount

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'role', 'faculty_type', 'is_active', 'last_login')
    list_filter = ('role', 'faculty_type', 'is_active', 'invitation_status')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('last_name', 'first_name')

@admin.register(FacultyAccount)
class FacultyAccountAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'faculty_type', 'is_active', 'invitation_status')
    list_filter = ('faculty_type', 'is_active', 'invitation_status')
    ordering = ('last_name', 'first_name')

    def save_model(self, request, obj, form, change):
        obj.role = obj.Role.FACULTY
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(role=User.Role.FACULTY)

@admin.register(StaffAccount)
class StaffAccountAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'is_active', 'invitation_status')
    ordering = ('last_name', 'first_name')
    
    def save_model(self, request, obj, form, change):
        obj.role = obj.Role.STAFF
        obj.faculty_type = obj.FacultyType.N_A
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(role=User.Role.STAFF)