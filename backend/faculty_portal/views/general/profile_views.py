from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from accounts.decorators import faculty
from accounts.forms import FacultyProfileForm

@faculty
@require_http_methods(['GET', 'POST'])
def profile_view(request):
    if request.method == 'POST':
        form = FacultyProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('faculty_portal:profile')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = FacultyProfileForm(instance=request.user)

    context = {'form': form}
    
    return render(
        request,
        'faculty_portal/general/profile.html',
        context
    )