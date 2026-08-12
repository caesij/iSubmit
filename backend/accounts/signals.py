from django.dispatch import receiver
from axes.signals import user_locked_out
from accounts.models import User

@receiver(user_locked_out)
def deactivate_on_lockout(sender, request, username, ip_address, **kwargs):
    if username:
        User.objects.filter(email=username).update(is_active=False, is_locked_out=True)