from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from accounts.decorators import role_required
from accounts.forms import AdminStaffProfileForm

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET', 'POST'])
def profile_view(request):
    if request.method == 'POST':
        form = AdminStaffProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('admin_staff_portal:profile')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = AdminStaffProfileForm(instance=request.user)

    context = {'form': form}
    
    return render(
        request,
        'admin_staff_portal/general/profile.html',
        context
    )