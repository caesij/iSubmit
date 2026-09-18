from accounts.models import NotificationPreference

def validate_portal_access(user, login_type):
    if login_type == 'FACULTY':
        if not user.is_faculty:
            return False, 'Only Faculty accounts can sign in through this tab.'
    elif login_type == 'ADMIN':
        if user.is_faculty:
            return False, 'Faculty members must sign in through the Faculty tab.'
        if not (user.is_admin or user.is_staff_role):
            return False, 'Access denied. Only Admin or Staff accounts can sign in here.'
            
    return True, None

def get_or_create_preferences(user):
    allowed_types = NotificationPreference.ROLE_TYPES.get(user.role, [])

    existing = {
        p.notification_type: p
        for p in NotificationPreference.objects.filter(
            user=user, notification_type__in=allowed_types
        )
    }

    to_create = []
    for value in allowed_types:
        if value not in existing:
            pref = NotificationPreference(user=user, notification_type=value)
            to_create.append(pref)
            existing[value] = pref

    if to_create:
        NotificationPreference.objects.bulk_create(to_create)

    return [existing[value] for value in allowed_types]