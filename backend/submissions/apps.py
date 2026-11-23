from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SubmissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "submissions"

    def ready(self):
        from submissions.signals import seed_requirement_templates

        post_migrate.connect(
            seed_requirement_templates,
            sender=self,
            dispatch_uid="submissions.seed_requirement_templates",
        )
