from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError
from django.db import connection

from submissions.models import SubmissionPeriod
from submissions.slots import sync_upload_slots


class Command(BaseCommand):
    help = "Automatically initializes and synchronizes the application database."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQL is required.")

        verbosity = options["verbosity"]

        # 1. Ensure the required PostgreSQL extension exists
        self.stdout.write("Checking PostgreSQL extensions...")

        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE SCHEMA IF NOT EXISTS extensions;"
            )
            cursor.execute(
                """
                CREATE EXTENSION IF NOT EXISTS pg_trgm
                WITH SCHEMA extensions;
                """
            )

        # 2. Apply all database migrations
        self.stdout.write("Applying database migrations...")

        call_command(
            "migrate",
            interactive=False,
            verbosity=verbosity,
        )

        # 3. Synchronize existing active submission periods
        self.stdout.write("Synchronizing upload slots...")

        periods = SubmissionPeriod.objects.filter(status=SubmissionPeriod.ReqStatus.ACTIVE)

        for period in periods:
            sync_upload_slots(period)

        self.stdout.write(self.style.SUCCESS("Database initialization completed."))
