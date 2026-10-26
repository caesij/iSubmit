from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.http import JsonResponse

from accounts.decorators import admin
from accounts.models import User
from notifications.forms import SystemNotificationForm
from notifications.models import Notification, NotificationPreference
from notifications.services import notify_roles
from notifications.helpers import get_role_based_notifications


@admin
@require_http_methods(['GET', 'POST'])
def create_system_notification_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Only administrator superusers can create system notifications.')

    if request.method == 'POST':
        form = SystemNotificationForm(request.POST)
        if form.is_valid():
            notifications = notify_roles(
                roles=[User.Role.FACULTY],
                notification_type=NotificationPreference.NotificationType.SYSTEM_NOTIFICATIONS,
                title=form.cleaned_data['title'],
                message=form.cleaned_data['message'],
            )
            
            count = len(notifications)
            
            messages.success(
                request,
                f'Created in-app system notifications for {count} '
                f'faculty account{"s" if count != 1 else ""}.',
            )
            return redirect('notifications:notification_list')
    else:
        form = SystemNotificationForm()
        
    context = {'form': form}

    return render(
        request,
        'admin_staff_portal/notifications/create_notification.html',
        context
    )


@login_required
@require_http_methods(['GET'])
def notification_list_data_view(request):
    context = get_role_based_notifications(request)

    paginator = Paginator(context.pop('notifications'), 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    context.update({
        'notifications': page_obj,
        'page_obj': page_obj,
    })

    if request.user.is_faculty:
        template = 'faculty_portal/notifications/_notifications_list.html'
    else:
        template = 'admin_staff_portal/notifications/_notifications_list.html'

    html = render_to_string(template, context, request=request)

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
        notification_type__in=NotificationPreference.ROLE_TYPES.get(request.user.role, [])
    ).count()

    return JsonResponse({
        'html': html,
        'unread_count': unread_count
    })


@login_required
@require_http_methods(['GET'])
def notification_list_view(request):
    context = get_role_based_notifications(request)

    paginator = Paginator(context.pop('notifications'), 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    context.update({
        'notifications': page_obj,
        'page_obj': page_obj,
    })

    if request.user.is_faculty:
        template = 'faculty_portal/notifications/notifications_list.html'
    else:
        template = 'admin_staff_portal/notifications/notifications_list.html'

    return render(request, template, context)



@login_required
@require_http_methods(['GET'])
def notification_dropdown_view(request):
    allowed_types = NotificationPreference.ROLE_TYPES.get(request.user.role, [])

    notifications = Notification.objects.filter(
        user=request.user,
        notification_type__in=allowed_types
    ).order_by('-created_at')[:3]

    unread_count = Notification.objects.filter(
        user=request.user,
        notification_type__in=allowed_types,
        is_read=False
    ).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }

    if request.user.is_faculty:
        template = 'faculty_portal/notifications/notif_dropdown.html'
    else:
        template = 'admin_staff_portal/notifications/notif_dropdown.html'

    html = render_to_string(template, context, request=request)

    return JsonResponse({
        'html': html,
        'unread_count': unread_count
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