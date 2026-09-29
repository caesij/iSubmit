from core.realtime import send_to_user


def refresh_faculty_dashboard(user):

    send_to_user(
        user,
        'dashboard.update',
    )