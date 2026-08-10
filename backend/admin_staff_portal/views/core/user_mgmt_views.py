from django.urls import reverse
from django.views.generic import ListView, CreateView, UpdateView, View
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q
from accounts.models import User
from admin_staff_portal.forms import UserManagementForm
from admin_staff_portal.mixins import AdminOrStaffRequiredMixin, RoleContextMixin
import secrets
import string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages

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
        context['page_title'] = "Faculty Management" if self.target_role == User.Role.FACULTY else "Staff Management"
        context['current_role'] = self.target_role
        context['form'] = UserManagementForm(
            request_user=self.request.user,
            initial_role=self.target_role
        )
        return context


class UserCreateView(AdminOrStaffRequiredMixin, RoleContextMixin, CreateView):
    model = User
    form_class = UserManagementForm
    template_name = 'admin_staff_portal/core/user_mgmt/user_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        kwargs['initial_role'] = self.target_role
        return kwargs

    def get_success_url(self):
        url = reverse('admin_staff_portal:user_list')
        return f"{url}?role={self.target_role}"

    def form_valid(self, form):
        user = form.save(commit=False)

        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        user.set_password(temp_password)
        user.save()

        # Email Notification (Account Credentials)
        subject = "Welcome to iSubmit - Your Account Credentials"
        message = (
            f"Hello {user.get_full_name()},\n\n"
            f"An account has been created for you on the iSubmit portal.\n\n"
            f"Email: {user.email}\n"
            f"Temporary Password: {temp_password}\n\n"
            f"Please log in and change your password immediately."
        )

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            messages.success(self.request, f"Account created for {user.email}. Password email sent successfully.")
        except Exception as e:
            messages.warning(self.request, f"Account created for {user.email}, but failed to send email: {str(e)}")

        return redirect(self.get_success_url())

class UserUpdateView(AdminOrStaffRequiredMixin, UpdateView):
    model = User
    form_class = UserManagementForm
    template_name = 'admin_staff_portal/core/user_mgmt/user_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        target_user = self.get_object()
        user = request.user

        if user.is_staff_role and target_user.role != User.Role.FACULTY:
            messages.error(request, "You do not have permission to edit this account.")
            return redirect('admin_staff_portal:user_list')

        if user.is_admin and target_user.role not in [User.Role.STAFF, User.Role.FACULTY]:
            messages.error(request, "You do not have permission to edit this account.")
            return redirect('admin_staff_portal:user_list')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        url = reverse('admin_staff_portal:user_list')

        if self.object.role == User.Role.FACULTY:
            return f"{url}?role=FACULTY"
        
        return f"{url}?role=STAFF"

class UserToggleAccStatusView(AdminOrStaffRequiredMixin, View):
    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        user = request.user

        # Authorization
        if user.is_staff_role and target_user.role != User.Role.FACULTY:
            return redirect('admin_staff_portal:user_list')

        if user.is_admin and target_user.role not in [User.Role.STAFF, User.Role.FACULTY]:
            return redirect('admin_staff_portal:user_list')

        target_user.is_active = not target_user.is_active
        target_user.save()

        redirect_url = reverse('admin_staff_portal:user_list')

        if target_user.role == User.Role.FACULTY:
            return redirect(f"{redirect_url}?role=FACULTY")
        return redirect(f"{redirect_url}?role=STAFF")