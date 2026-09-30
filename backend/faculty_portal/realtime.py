from core.realtime import send_to_user

def refresh_faculty_dashboard(user):

    send_to_user(
        user,
        'dashboard.update',
    )

def refresh_faculty_submission_bin(user):
    send_to_user(user, "submission_bin.update")

def refresh_all_faculty_submission_bins():
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "faculty_submission_bins",
        {
            "type": "realtime_event",
            "event": "submission_bin.update",
            "data": {},
        },
    )