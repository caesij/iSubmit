from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.http import JsonResponse


from notifications.models import Notification, NotificationPreference


@login_required
@require_http_methods(['GET'])
def notification_list_data_view(request):
    notifications = Notification.objects.filter(user=request.user)

    notification_type = request.GET.get('type')
    read_status = request.GET.get('read')
    sort_by = request.GET.get('sort', 'newest')

    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)

    if read_status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_status == 'read':
        notifications = notifications.filter(is_read=True)

    if sort_by == 'oldest':
        notifications = notifications.order_by('created_at')
    else:
        notifications = notifications.order_by('-created_at')

    paginator = Paginator(notifications, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'notifications': page_obj,
        'page_obj': page_obj,
        'notification_types': NotificationPreference.NotificationType.choices,
        'selected_type': notification_type or '',
        'selected_read': read_status or '',
        'selected_sort': sort_by,
    }

    if request.user.is_faculty:
        template = 'faculty_portal/notifications/_notifications_list.html'
    else:
        template = 'admin_staff_portal/notifications/_notifications_list.html'

    html = render_to_string(
        template,
        context,
        request=request,
    )

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    return JsonResponse({
        'html': html,
        'unread_count': unread_count,
    })


@login_required
@require_http_methods(['GET'])
def notification_list_view(request):
    notifications = Notification.objects.filter(user=request.user)

    notification_type = request.GET.get('type')
    read_status = request.GET.get('read')
    sort_by = request.GET.get('sort', 'newest')

    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)

    if read_status == 'unread':
        notifications = notifications.filter(
            is_read=False
        )
    elif read_status == 'read':
        notifications = notifications.filter(
            is_read=True
        )

    if sort_by == 'oldest':
        notifications = notifications.order_by('created_at')
    else:
        notifications = notifications.order_by('-created_at')

    paginator = Paginator(notifications, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'notifications': page_obj,
        'page_obj': page_obj,
        'notification_types': NotificationPreference.NotificationType.choices,
        'selected_type': notification_type or '',
        'selected_read': read_status or '',
        'selected_sort': sort_by,
    }
    
    if request.user.is_faculty:
        template = 'faculty_portal/notifications/notifications_list.html'
    else:
        template = 'admin_staff_portal/notifications/notifications_list.html'

    return render(request, template, context)


@login_required
@require_http_methods(['GET'])
def notification_dropdown_view(request):
    notifications = (
        Notification.objects
        .filter(user=request.user)
        .order_by('-created_at')[:3]
    )

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    if request.user.is_faculty:
        template = ('faculty_portal/notifications/notif_dropdown.html')
    else:
        template = ('admin_staff_portal/notifications/notif_dropdown.html')

    html = render_to_string(
        template,
        {
            'notifications': notifications,
            'unread_count': unread_count,
        },
        request=request,
    )

    return JsonResponse({
        'html': html,
        'unread_count': unread_count,
    })


@login_required
@require_http_methods(['POST'])
def mark_notification_read_view(request, notification_id):
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )

    notification.is_read = True
    notification.save(update_fields=['is_read'])

    if notification.link:
        return redirect(notification.link)

    return redirect('notifications:notification_list')


@login_required
@require_http_methods(['POST'])
def mark_all_notifications_read_view(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    return redirect('notifications:notification_list')