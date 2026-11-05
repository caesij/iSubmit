from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from accounts.decorators import role_required
from accounts.forms import FacultyProfileForm

@role_required('FACULTY')
@require_http_methods(['GET', 'POST'])
def profile_view(request):
    if request.method == 'POST':
        form = FacultyProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('faculty_portal:profile')
        messages.error(request, 'We could not save your profile. Please review the highlighted fields.')
    else:
        form = FacultyProfileForm(instance=request.user)

    context = {'form': form}
    
    return render(
        request,
        'faculty_portal/general/profile.html',
        context
    )