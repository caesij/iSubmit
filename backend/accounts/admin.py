from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from accounts.models import (
    User,
    FacultyAccount,
    StaffAccount,
    StaffPermission,
    SecurityLoginRecord
)


# User Forms
COMMON_USER_FIELDS = (
    'email',
    'first_name',
    'middle_name',
    'last_name',
    'employee_ID'
)

class UserCreationAdminForm(UserCreationForm):
    class Meta:
        model = User
        fields = COMMON_USER_FIELDS + (
            'role',
            'faculty_type',
            'assigned_programs',
        )


class UserChangeAdminForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


class FacultyCreationAdminForm(UserCreationForm):
    class Meta:
        model = FacultyAccount
        fields = COMMON_USER_FIELDS + (
            'faculty_type',
            'assigned_programs',
        )


class FacultyChangeAdminForm(UserChangeForm):
    class Meta:
        model = FacultyAccount
        fields = '__all__'


class StaffCreationAdminForm(UserCreationForm):
    class Meta:
        model = StaffAccount
        fields = COMMON_USER_FIELDS


class StaffChangeAdminForm(UserChangeForm):
    class Meta:
        model = StaffAccount
        fields = '__all__'


# Shared Account Configuration
class BaseRoleAccountAdmin(BaseUserAdmin):
    ordering = ('email',)

    search_fields = (
        'email',
        'employee_ID',
        'first_name',
        'middle_name',
        'last_name',
    )

    readonly_fields = (
        'last_login',
        'date_joined',
        'updated_at',
        'is_locked_out',
        'locked_out_until',
    )

    save_on_top = True


# Faculty Account
@admin.register(FacultyAccount)
class FacultyAccountAdmin(BaseRoleAccountAdmin):
    form = FacultyChangeAdminForm
    add_form = FacultyCreationAdminForm

    list_display = (
        'first_name',
        'middle_name',
        'last_name',
        'email',
        'employee_ID',
        'faculty_type',
        'is_active',
    )

    list_filter = (
        'faculty_type',
        'is_active',
    )

    filter_horizontal = ('assigned_programs',)

    fieldsets = (
        ('Account Information', {
            'fields': ('email', 'password', 'employee_ID')
        }),
        ('Personal Information', {
            'fields': (
                'first_name',
                'middle_name',
                'last_name',
                'profile_picture',
            )
        }),
        ('Faculty Information', {
            'fields': (
                'faculty_type',
                'assigned_programs',
            )
        }),
        ('User Preferences', {
            'fields': (
                'timezone',
                'date_format',
                'time_format',
            )
        }),
        ('Account Status', {
            'fields': ('is_active',)
        }),
        ('Security Information', {
            'fields': (
                'is_locked_out',
                'locked_out_until',
            )
        }),
        ('Important Dates', {
            'fields': (
                'last_login',
                'date_joined',
                'updated_at',
            )
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'first_name',
                'middle_name',
                'last_name',
                'employee_ID',
                'faculty_type',
                'assigned_programs',
                'password1',
                'password2',
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.role = User.Role.FACULTY
        super().save_model(request, obj, form, change)


# Staff Account
@admin.register(StaffAccount)
class StaffAccountAdmin(BaseRoleAccountAdmin):
    form = StaffChangeAdminForm
    add_form = StaffCreationAdminForm

    list_display = (
        'first_name',
        'middle_name',
        'last_name',
        'email',
        'employee_ID',
        'is_active',
    )

    list_filter = ('is_active',)

    fieldsets = (
        ('Account Information', {
            'fields': ('email', 'password', 'employee_ID')
        }),
        ('Personal Information', {
            'fields': (
                'first_name',
                'middle_name',
                'last_name',
                'profile_picture',
            )
        }),
        ('User Preferences', {
            'fields': (
                'timezone',
                'date_format',
                'time_format',
            )
        }),
        ('Account Status', {
            'fields': ('is_active',)
        }),
        ('Security Information', {
            'fields': (
                'is_locked_out',
                'locked_out_until',
            )
        }),
        ('Important Dates', {
            'fields': (
                'last_login',
                'date_joined',
                'updated_at',
            )
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'first_name',
                'middle_name',
                'last_name',
                'employee_ID',
                'password1',
                'password2',
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.role = User.Role.STAFF
        super().save_model(request, obj, form, change)


# Superuser Account
@admin.register(User)
class UserAdmin(BaseRoleAccountAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm

    list_display = (
        'first_name',
        'middle_name',
        'last_name',
        'email',
        'employee_ID',
        'role',
        'is_staff',
        'is_superuser',
        'is_active',
    )

    list_filter = (
        'role',
        'faculty_type',
        'is_active',
        'is_staff',
        'is_superuser',
    )

    filter_horizontal = (
        'assigned_programs',
        'groups',
        'user_permissions',
    )

    fieldsets = (
        ('Account Information', {
            'fields': ('email', 'password', 'employee_ID')
        }),
        ('Personal Information', {
            'fields': (
                'first_name',
                'middle_name',
                'last_name',
                'profile_picture',
            )
        }),
        ('Role and Assignment', {
            'fields': (
                'role',
                'faculty_type',
                'assigned_programs',
            )
        }),
        ('User Preferences', {
            'fields': (
                'timezone',
                'date_format',
                'time_format',
            )
        }),
        ('Account Permissions', {
            'fields': (
                'is_active',
                'groups',
                'user_permissions',
            )
        }),
        ('Security Information', {
            'fields': (
                'is_locked_out',
                'locked_out_until',
            )
        }),
        ('Important Dates', {
            'fields': (
                'last_login',
                'date_joined',
                'updated_at',
            )
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'first_name',
                'middle_name',
                'last_name',
                'employee_ID',
                'role',
                'faculty_type',
                'assigned_programs',
                'password1',
                'password2',
            ),
        }),
    )


# Staff Permissions
@admin.register(StaffPermission)
class StaffPermissionAdmin(admin.ModelAdmin):
    list_display = (
        'review_faculty_submissions',
        'return_for_revisions',
        'manage_submission_bins',
        'view_approved_documents',
        'add_faculty_users',
        'updated_at',
    )

    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and not StaffPermission.objects.exists()
        )

    def has_delete_permission(self, request, obj=None):
        return False


# Security Login Records
@admin.register(SecurityLoginRecord)
class SecurityLoginRecordAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'user_agent',
        'first_seen',
        'last_seen',
        'expires_at',
    )

    search_fields = (
        'user__email',
        'user__employee_ID',
        'user__first_name',
        'user__last_name',
        'user_agent',
    )

    list_filter = ('first_seen', 'last_seen')

    date_hierarchy = 'first_seen'

    readonly_fields = tuple(
        field.name
        for field in SecurityLoginRecord._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False