from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator

from accounts.decorators import role_required
from programs.models import Program
from programs.forms import ProgramForm

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def program_list(request):
    programs = Program.objects.all().order_by('program_name')
    
    paginator = Paginator(programs, 7)
    
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'programs': page_obj,
        'page_obj': page_obj
    }
    
    return render(
        request, 
        'admin_staff_portal/core/user_mgmt/program_list.html', 
        context
    )


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def add_program(request):
    if request.method == 'POST':
        form = ProgramForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Program added successfully.')

    return redirect('admin_staff_portal:program_list')


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def update_program(request, program_id):
    if request.method == 'POST':
        program = get_object_or_404(Program, pk=program_id)
        form = ProgramForm(request.POST, instance=program)
        if form.is_valid():
            form.save()
            messages.success(request, f'Program updated successfully.')

    return redirect('admin_staff_portal:program_list')


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def delete_program(request, program_id):
    if request.method == 'POST':
        program = get_object_or_404(Program, pk=program_id)
        program.delete()
        messages.success(request, f'Program deleted successfully.')
    
    return redirect('admin_staff_portal:program_list')