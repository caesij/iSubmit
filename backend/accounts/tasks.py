from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone


@shared_task
def release_expired_account_lockouts():
    User = get_user_model()

    expired_accounts = User.objects.filter(
        is_locked_out=True,
    ).filter(
        Q(locked_out_until__lte=timezone.now())
        | Q(locked_out_until__isnull=True)
    )

    return expired_accounts.update(
        is_locked_out=False,
        locked_out_until=None,
    )