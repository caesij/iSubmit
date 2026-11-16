from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required, staff_permission_required
from submissions.helpers import get_requirement_rows
from submissions.models import Requirement, SubmissionPeriod
from submissions.services import publish_updates, save_requirements
from submissions.forms import PeriodForm, RequirementFormSet
from submissions.slots import sync_upload_slots

TEMPLATE_DIR = 'admin_staff_portal/core/submissions/submission_bin/'
PERIODS_PER_PAGE = 10


def manage_bins_only(view):
    return role_required('ADMIN', 'STAFF')(staff_permission_required('manage_submission_bins')(view))


# List of all submission periods
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def requirements_list(request):
    periods = SubmissionPeriod.objects.with_progress()

    query = request.GET.get('q')
    semester = request.GET.get('semester')
    academic_year = request.GET.get('academic_year')

    if query:
        matching_requirements = Requirement.objects.filter(requirement_title__icontains=query)
        periods = periods.filter(
            Q(academic_year__icontains=query) | Q(pk__in=matching_requirements.values('period'))
        )
    if semester:
        periods = periods.filter(semester=semester)
    if academic_year:
        periods = periods.filter(academic_year=academic_year)

    page_obj = Paginator(periods, PERIODS_PER_PAGE).get_page(request.GET.get('page'))

    filters = request.GET.copy()
    filters.pop('page', None)

    context = {
        'periods': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'query_string': filters.urlencode(),
        'semester_choices': SubmissionPeriod.Semester.choices,
        'academic_years': SubmissionPeriod.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year'),
    }

    return render(request, TEMPLATE_DIR + 'requirements_list.html', context)


# List of every requirement
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def period_detail(request, period_id):
    period = get_object_or_404(SubmissionPeriod.objects.with_progress(), pk=period_id)

    context = {
        'period': period,
        'requirements': period.requirements.with_progress(),
    }

    return render(request, TEMPLATE_DIR + 'period_detail.html', context)


@manage_bins_only
@require_http_methods(['GET', 'POST'])
def period_editor(request, period_id=None):
    # Create or edit a submission period
    period = get_object_or_404(SubmissionPeriod, pk=period_id) if period_id else None
    posted = request.POST or None

    period_form = PeriodForm(posted, instance=period)
    formset = RequirementFormSet(posted, initial=get_requirement_rows(period))

    if request.method == 'POST' and all([period_form.is_valid(), formset.is_valid()]):
        is_new = period is None
        deadline_changed = 'deadline' in period_form.changed_data
        notice = 'created' if is_new else 'deadline_changed' if deadline_changed else None

        with transaction.atomic():
            period = period_form.save(commit=False)
            if is_new:
                period.created_by = request.user
            period.save()

            save_requirements(period, formset.cleaned_data)
            sync_upload_slots(period)
            transaction.on_commit(lambda: publish_updates(period, notice))

        messages.success(request, f'{period} saved.')
        if period.deadline < timezone.now():
            messages.warning(request, 'This deadline has already passed. Faculty will see the requirements as overdue.')

        return redirect('admin_staff_portal:period_detail', period_id=period.pk)

    context = {
        'period': period,
        'period_form': period_form,
        'formset': formset,
    }

    return render(request, TEMPLATE_DIR + 'period_editor.html', context)


def _toggle_status(request, model, pk, message):
    with transaction.atomic():
        obj = get_object_or_404(model.objects.select_for_update(), pk=pk)
        obj.toggle_status()
        transaction.on_commit(publish_updates)

    messages.success(request, message)
    return obj


def _redirect_back(request, fallback_url):
    next_url = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback_url)


@manage_bins_only
@require_http_methods(['POST'])
def toggle_period_status(request, period_id):
    _toggle_status(request, SubmissionPeriod, period_id, 'Period status updated.')
    return _redirect_back(request, reverse('admin_staff_portal:requirements_list'))


@manage_bins_only
@require_http_methods(['POST'])
def toggle_requirement_status(request, requirement_id):
    requirement = _toggle_status(request, Requirement, requirement_id, 'Requirement status updated.')
    return _redirect_back(request, reverse('admin_staff_portal:period_detail', args=[requirement.period_id]))
