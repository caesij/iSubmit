from django.contrib import admin

from notifications.models import Notification, NotificationPreference

# Notification Preference Management for Superuser
@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'notification_type',
        'enabled',
        'email_enabled',
        'system_enabled',
    )

    list_filter = (
        'notification_type',
        'enabled',
        'email_enabled',
        'system_enabled',
    )

    search_fields = (
        'user__email',
        'user__employee_ID',
        'user__first_name',
        'user__last_name',
    )

    raw_id_fields = ('user',)


# Notification Management for Superuser
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'title',
        'notification_type',
        'is_read',
        'created_at',
    )

    list_filter = (
        'notification_type',
        'is_read',
        'created_at',
    )

    search_fields = (
        'user__email',
        'user__employee_ID',
        'title',
        'message',
    )

    raw_id_fields = ('user',)

    readonly_fields = ('created_at',)

    date_hierarchy = 'created_at'

    actions = (
        'mark_as_read',
        'mark_as_unread',
    )

    @admin.action(description='Mark selected notifications as read')
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description='Mark selected notifications as unread')
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)