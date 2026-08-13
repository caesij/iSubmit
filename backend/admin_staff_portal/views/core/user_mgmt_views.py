from django.urls import reverse
from django.views.generic import ListView, CreateView, UpdateView, View
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q
from accounts.models import User
from admin_staff_portal.forms import StaffManagementForm, FacultyManagementForm
from admin_staff_portal.mixins import AdminOrStaffRequiredMixin, RoleContextMixin, RoleFormMixin
import secrets
import string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from axes.utils import reset as axes_reset

class UserListView(AdminOrStaffRequiredMixin, RoleContextMixin, ListView):
    model = User
    template_name = 'admin_staff_portal/core/user_mgmt/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        search_query = self.request.GET.get('q', '').strip()
        faculty_type_param = self.request.GET.get('faculty_type', '').strip()
        status_param = self.request.GET.get('status', '').strip().lower()

        queryset = User.objects.filter(role=self.target_role)

        # Filtering by Name or Email (Search Bar)
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(middle_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query)
            )

        # Faculty Type Filtering
        if self.target_role == User.Role.FACULTY and faculty_type_param:
            queryset = queryset.filter(faculty_type=faculty_type_param)

        # Account Status Filtering
        if status_param == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_param == 'inactive':
            queryset = queryset.filter(is_active=False)

        return queryset

    # Context Passing for Pages
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form_class = FacultyManagementForm if self.target_role == User.Role.FACULTY else StaffManagementForm
        context['form'] = form_class(request_user=self.request.user)
        return context


class UserCreateView(AdminOrStaffRequiredMixin, RoleContextMixin, RoleFormMixin, CreateView):
    model = User

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def get_success_url(self):
        url = reverse('admin_staff_portal:user_list')
        return f"{url}?role={self.target_role}"

    def form_valid(self, form):
        user = form.save(commit=False)

        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        generated_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        user.set_password(generated_password)
        user.save()

        # Email Notification (Account Credentials)
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
            messages.success(self.request, f'Account created for {user.email}. Password email sent successfully.')
        except Exception:
            messages.warning(self.request, f'Account created for {user.email}, but failed to send email.')

        return redirect(self.get_success_url())

class UserUpdateView(AdminOrStaffRequiredMixin, RoleContextMixin, RoleFormMixin, UpdateView):
    model = User

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        target_user = self.get_object()

        if not self.can_manage_target(target_user):
            messages.error(request, "You do not have permission to edit this account.")
            return redirect('admin_staff_portal:user_list')

        self.target_role = target_user.role
        
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        url = reverse('admin_staff_portal:user_list')
        return f'{url}?role={self.object.role}'

class UserToggleAccStatusView(AdminOrStaffRequiredMixin, View):
    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        redirect_url = f"{reverse('admin_staff_portal:user_list')}?role={target_user.role}"

        if request.user.pk == target_user.pk:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect(redirect_url)

        if not self.can_manage_target(target_user):
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