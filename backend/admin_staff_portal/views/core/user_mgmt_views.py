from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
import secrets
import string
from axes.utils import reset as axes_reset

from accounts.decorators import role_required
from admin_staff_portal.helpers import (
    get_target_role,
    get_page_title,
    get_form_class,
    get_form_template,
    can_manage_target,
)

User = get_user_model()

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def user_list_view(request):
    target_role = get_target_role(request)

    search_query = request.GET.get('q', '').strip()
    faculty_type_param = request.GET.get('faculty_type', '').strip()
    status_param = request.GET.get('status', '').strip().lower()

    users = User.objects.filter(role=target_role)

    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(middle_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    if target_role == User.Role.FACULTY and faculty_type_param:
        users = users.filter(faculty_type=faculty_type_param)

    if status_param == 'active':
        users = users.filter(is_active=True)
    elif status_param == 'inactive':
        users = users.filter(is_active=False)

    form_class = get_form_class(target_role)

    context = {
        'users': users,
        'target_role': target_role,
        'current_role': target_role,
        'page_title': get_page_title(target_role),
        'form': form_class(request_user=request.user),
    }
    
    return render(
        request, 
        'admin_staff_portal/core/user_mgmt/user_list.html', 
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET', 'POST'])
def user_create_view(request):
    target_role = get_target_role(request)
    form_class = get_form_class(target_role)

    if request.method == 'POST':
        form = form_class(request.POST, request_user=request.user)
        if form.is_valid():
            user = form.save(commit=False)

            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            generated_password = ''.join(secrets.choice(alphabet) for _ in range(12))
            user.set_password(generated_password)
            user.save()

            subject = 'Welcome to iSubmit - Your Account Credentials'
            message = (
                f'Hello {user.get_full_name()},\n\n'
                f'An account has been created for you on the iSubmit portal.\n\n'
                f'Email: {user.email}\n'
                f'Password: {generated_password}\n\n'
            )

            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                messages.success(request, f'Account created for {user.email}. Password email sent successfully.')
            except Exception:
                messages.warning(request, f'Account created for {user.email}, but failed to send email.')

            url = reverse('admin_staff_portal:user_list')
            return redirect(f"{url}?role={target_role}")
    else:
        form = form_class(request_user=request.user)

    context = {
        'form': form,
        'target_role': target_role,
        'current_role': target_role,
        'page_title': get_page_title(target_role),
    }
    
    return render(
        request, 
        get_form_template(target_role), 
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET', 'POST'])
def user_update_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if not can_manage_target(request.user, target_user):
        messages.error(request, 'You do not have permission to edit this account.')
        return redirect('admin_staff_portal:user_list')

    target_role = target_user.role
    form_class = get_form_class(target_role)

    if request.method == 'POST':
        form = form_class(request.POST, instance=target_user, request_user=request.user)
        if form.is_valid():
            form.save()
            url = reverse('admin_staff_portal:user_list')
            return redirect(f"{url}?role={target_user.role}")
    else:
        form = form_class(instance=target_user, request_user=request.user)

    context = {
        'form': form,
        'target_role': target_role,
        'current_role': target_role,
        'page_title': get_page_title(target_role),
        'object': target_user,
    }
    
    return render(
        request, 
        get_form_template(target_role), 
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def user_toggle_acc_status_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    redirect_url = f"{reverse('admin_staff_portal:user_list')}?role={target_user.role}"

    if request.user.pk == target_user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect(redirect_url)

    if not can_manage_target(request.user, target_user):
        messages.error(request, 'You do not have permission to edit this account status.')
        return redirect(redirect_url)

    target_user.is_active = not target_user.is_active

    if target_user.is_active:
        target_user.is_locked_out = False
        axes_reset(username=target_user.email)

    target_user.save()

    status_label = 'activated' if target_user.is_active else 'deactivated'
    messages.success(request, f'The account has been {status_label}.')

    return redirect(redirect_url)