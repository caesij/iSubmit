from django.contrib import admin
from .models import User, FacultyAccount, StaffAccount

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'is_staff', 'is_superuser')

@admin.register(FacultyAccount)
class FacultyAccountAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name')

    def save_model(self, request, obj, form, change):
        obj.role = obj.Role.FACULTY
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset().filter(role=User.Role.FACULTY)

@admin.register(StaffAccount)
class StaffAccountAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name')
    
    def save_model(self, request, obj, form, change):
        obj.role = obj.Role.STAFF
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset().filter(role=User.Role.STAFF)