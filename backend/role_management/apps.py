from django.apps import AppConfig


class RoleManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'role_management'
    verbose_name = 'Role Management'

    def ready(self):
        from role_management import signals  # noqa: F401
