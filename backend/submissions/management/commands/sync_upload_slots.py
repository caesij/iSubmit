from django.core.management.base import BaseCommand

from submissions.models import SubmissionPeriod
from submissions.slots import sync_upload_slots


class Command(BaseCommand):
    help = (
        'Rebuilds the upload slots (who owes what) from the teaching load. '
        'Run it after importing teaching loads in bulk or re-activating a faculty account. Safe to run any time.'
    )

    def handle(self, *args, **options):
        for period in SubmissionPeriod.objects.filter(status=SubmissionPeriod.ReqStatus.ACTIVE):
            sync_upload_slots(period)
            self.stdout.write(f'Synced {period}')
