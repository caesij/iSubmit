from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.urls import reverse
from django.views.decorators.http import require_http_methods


from accounts.decorators import role_required
from programs.models import Program, ProgramSection, ProgramCourse
from submissions.models import ClassAssignment, Course
from programs.forms import current_academic_year

from programs.forms import (
    ProgramForm,
    ProgramSectionForm,
    ProgramCourseForm,
    CourseForm,
    current_academic_year,
    academic_year_choices,
)

TEMPLATE_DIR = 'admin_staff_portal/core/program_mgmt'
PROGRAMS_PER_PAGE = 7
COURSES_PER_PAGE = 15

# Program Management
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def program_list(request):

    programs = Program.objects.annotate(
        section_count=Count('sections', distinct=True),
        course_count=Count('program_courses', distinct=True)
    )

    page_obj = Paginator(programs, PROGRAMS_PER_PAGE).get_page(request.GET.get('page'))
    
    context = {
        'programs': page_obj,
        'page_obj': page_obj
    }

    return render(request, f'{TEMPLATE_DIR}/program_list.html', context)


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def add_program(request):

    form = ProgramForm(request.POST)

    if form.is_valid():
        form.save()
        messages.success(request, 'Program added successfully.')
    else:
        messages.error(request, form.errors.as_text())

    return redirect('admin_staff_portal:program_list')


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def update_program(request, program_id):

    program = get_object_or_404(Program, pk=program_id)
    form = ProgramForm(request.POST, instance=program)

    if form.is_valid():
        form.save()
        messages.success(request, 'Program updated successfully.')
    else:
        messages.error(request, form.errors.as_text())

    return redirect('programs:program_list')


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def delete_program(request, program_id):

    program = get_object_or_404(Program, pk=program_id)

    # Preserve existing faculty assignments
    if ClassAssignment.objects.filter(program=program).exists():
        messages.error(
            request,
            'This program cannot be deleted because requirements are assigned to faculty members.'
        )
    else:
        program.delete()
        messages.success(request, 'Program deleted successfully.')

    return redirect('programs:program_list')


# Program Details
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def program_detail(request, program_id):
    program = get_object_or_404(Program.objects.prefetch_related('sections', 'program_courses__course'), pk=program_id)

    # Available academic years
    academic_years = [year for year, _ in academic_year_choices(program)]

    current_year = current_academic_year()

    selected_year = request.GET.get('academic_year', current_year)

    # Validate selected academic year
    if selected_year not in academic_years:
        selected_year = current_year

    sections = program.sections.filter(academic_year=selected_year)

    context = {
        'program': program,
        'sections': sections,
        'program_courses': program.program_courses.select_related('course'),

        'academic_years': academic_years,
        'selected_academic_year': selected_year,

        'section_form': ProgramSectionForm(
            program=program,
            initial={'academic_year': selected_year},
        ),

        'course_form': ProgramCourseForm(program=program)
    }

    return render(request, f'{TEMPLATE_DIR}/program_detail.html', context)


# Program Section Management
@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def add_program_section(request, program_id):
    program = get_object_or_404(Program, pk=program_id)
    form = ProgramSectionForm(request.POST, program=program)
    academic_year = request.POST.get('academic_year', current_academic_year())

    if form.is_valid():
        section = form.save(commit=False)
        section.program = program
        section.save()

        academic_year = form.cleaned_data['academic_year']

        messages.success(request, 'Section added successfully.')
    else:
        messages.error(request, form.errors.as_text())

    url = reverse('programs:program_detail', kwargs={'program_id': program.pk})

    return redirect(f'{url}?{urlencode({"academic_year": academic_year})}')


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def update_program_section(request, program_id, section_id):
    program = get_object_or_404(Program, pk=program_id)
    section = get_object_or_404(ProgramSection, pk=section_id, program=program)
    form = ProgramSectionForm(request.POST, instance=section, program=program)

    if form.is_valid():
        form.save()
        messages.success(request, 'Section updated successfully.')
    else:
        messages.error(request, form.errors.as_text())

    return redirect('programs:program_detail', program_id=program.pk)


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def delete_program_section(request, program_id, section_id):
    program = get_object_or_404(Program, pk=program_id)
    section = get_object_or_404(ProgramSection, pk=section_id, program=program)

    in_use = ClassAssignment.objects.filter(
        program=program,
        academic_year=section.academic_year,
        year_level=section.year_level,
        section=str(section.section),
    ).exists()

    if in_use:
        messages.error(request, 'This section cannot be deleted because requirements are assigned to faculty members.')
    else:
        section.delete()
        messages.success(request, 'Section deleted successfully.')

    return redirect('programs:program_detail', program_id=program.pk)


# Program Course Management
@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def attach_program_course(request, program_id):
    program = get_object_or_404(Program, pk=program_id)

    form = ProgramCourseForm(request.POST, program=program)

    if form.is_valid():
        program_course = form.save(commit=False)
        program_course.program = program
        program_course.save()

        messages.success(request, 'Course added to program successfully.')
    else:
        messages.error(request, form.errors.as_text())

    return redirect('programs:program_detail', program_id=program.pk)


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def remove_program_course(request, program_id, program_course_id):
    program = get_object_or_404(Program, pk=program_id)
    program_course = get_object_or_404(ProgramCourse, pk=program_course_id, program=program)

    in_use = ClassAssignment.objects.filter(program=program, course=program_course.course).exists()

    if in_use:
        messages.error(request, 'This course cannot be removed because requirements are assigned to faculty members.')
    else:
        program_course.delete()
        messages.success(request, 'Course removed from program successfully.')

    return redirect('programs:program_detail', program_id=program.pk)


# Course Catalogue
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def course_list(request):

    courses = Course.objects.annotate(
        program_count=Count('program_links', distinct=True),
        assignment_count=Count('class_assignments', distinct=True),
    ).order_by('code')

    page_obj = Paginator(courses, COURSES_PER_PAGE).get_page(request.GET.get('page'))
    
    context = {
        'courses': page_obj,
        'page_obj': page_obj,
        'course_form': CourseForm(),
    }

    return render(request, f'{TEMPLATE_DIR}/course_list.html', context)


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def add_course(request):
    form = CourseForm(request.POST)

    if form.is_valid():
        form.save()
        messages.success(request, 'Course added successfully.')
    else:
        messages.error(request, form.errors.as_text())

    return redirect('programs:course_list')


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def update_course(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    old_classification = (course.is_ojt, course.has_lab)
    form = CourseForm(request.POST, instance=course)

    if form.is_valid():
        course = form.save()

        new_classification = (course.is_ojt, course.has_lab)

        if old_classification != new_classification:
            from submissions.slots import sync_course_periods

            transaction.on_commit(lambda course_id=course.pk: sync_course_periods(course_id))

        messages.success(request, 'Course updated successfully.')
    else:
        messages.error(request, form.errors.as_text())

    return redirect('programs:course_list')


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def delete_course(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    in_use = (course.program_links.exists() or course.class_assignments.exists())

    if in_use:
        messages.error(
            request,
            'This course cannot be deleted because it is used by a program or faculty assignment.'
        )
    else:
        course.delete()
        messages.success(request, 'Course deleted successfully.')

    return redirect('programs:course_list')
