from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Case, Count, Exists, ExpressionWrapper, F, OuterRef, Q, Value, When


def get_target_faculty_queryset(requirement=None):
    User = get_user_model()
    faculty = User.objects.filter(role=User.Role.FACULTY, is_active=True)

    if requirement is not None:
        faculty = faculty.filter(upload_slots__requirement=requirement).distinct()

    return faculty


def get_faculty_assigned_requirements(faculty):
    from submissions.models import Requirement

    return (
        Requirement.objects.active()
        .filter(slots__faculty=faculty)
        .select_related('period')
        .distinct()
    )


def get_requirement_rows(period=None):
    from submissions.models import DocumentMetadata, Requirement, RequirementTemplate

    fields = Requirement.SETTING_FIELDS

    if period is None:
        templates = RequirementTemplate.objects.filter(is_active=True)
        return list(templates.annotate(include=Value(True)).values(*fields, 'include'))

    saved = period.requirements.annotate(
        include=ExpressionWrapper(Q(status=Requirement.ReqStatus.ACTIVE), output_field=BooleanField()),
        locked=Exists(DocumentMetadata.objects.filter(requirement=OuterRef('pk'))),
    )
    return list(saved.values('id', *fields, 'include', 'locked'))


COMPLIANCE_CHOICES = [('approved', 'Approved'), ('complete', 'Complete'), ('incomplete', 'Incomplete')]


def annotate_upload_progress(faculty):
    from submissions.models import DocumentSubmission, active_q, required_q

    owed = active_q('upload_slots__requirement__') & required_q('upload_slots__requirement__')
    status = DocumentSubmission.SubmissionStatus

    return faculty.annotate(
        total_count=Count('upload_slots', filter=owed),
        submitted_count=Count(
            'upload_slots__submission',
            filter=owed & ~Q(upload_slots__submission__status=status.NEEDS_REVISION),
        ),
        approved_count=Count(
            'upload_slots__submission',
            filter=owed & Q(upload_slots__submission__status=status.APPROVED),
        ),
    ).annotate(
        compliance_status=Case(
            When(total_count__gt=0, approved_count=F('total_count'), then=Value('approved')),
            When(total_count__gt=0, submitted_count=F('total_count'), then=Value('complete')),
            default=Value('incomplete'),
        )
    )
