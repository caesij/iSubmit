from urllib.parse import urlencode
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from submissions.models import DocumentSubmission, Requirement
from submissions.helpers import get_faculty_assigned_requirements
from core.search_utils import all_terms_query

User = get_user_model()

FACULTY_SEARCH_FIELDS = (
    'faculty__first_name',
    'faculty__middle_name',
    'faculty__last_name',
)

RESULT_LIMIT = 4

_NAVIGATION = {
    'admin': (
        ('Dashboard', 'admin_staff_portal:admin_dashboard', ('dashboard',)),
        
        ('Documents', 'admin_staff_portal:document_repo', ('documents', 'document repository')),
        ('Document Archive', 'admin_staff_portal:document_archive', ('document archive', 'archive')),
        
        ('Submissions', 'admin_staff_portal:requirements_list', ('submissions', 'submission')),
        ('Submissions > Submission Bin', 'admin_staff_portal:requirements_list', ('submission bin', 'requirements')),
        ('Submissions > Faculty Submissions', 'admin_staff_portal:faculty_submissions_list', ('faculty submissions',)),
        
        ('Staff Management', 'admin_staff_portal:user_list', ('staff management',)),
        ('Faculty Management', 'admin_staff_portal:user_list', ('faculty management',)),
        
        ('Notifications', 'notifications:notification_list', ('notifications',)),
        
        ('Settings', 'admin_staff_portal:preferences', ('settings',)),
        ('Settings > Preferences', 'admin_staff_portal:preferences', ('preferences',)),
        ('Settings > Notification Settings', 'admin_staff_portal:notification_settings', ('notification settings',)),
        ('Settings > Accounts and Security', 'admin_staff_portal:account_and_security', ('accounts and security',)),
        ('Settings > Staff Permissions', 'admin_staff_portal:staff_permissions', ('staff permissions',)),
        
        ('Profile', 'admin_staff_portal:profile', ('profile',))
    ),
    
    'staff': (
        ('Dashboard', 'admin_staff_portal:staff_dashboard', ('dashboard',)),
        
        ('Documents', 'admin_staff_portal:document_repo', ('documents', 'document repository')),
        
        ('Submissions', 'admin_staff_portal:requirements_list', ('submissions', 'submission')),
        ('Submissions > Submission Bin', 'admin_staff_portal:requirements_list', ('submission bin', 'requirements')),
        ('Submissions > Faculty Submissions', 'admin_staff_portal:faculty_submissions_list', ('faculty submissions',)),
        
        ('Faculty Management', 'admin_staff_portal:user_list', ('faculty management',)),
        
        ('Notifications', 'notifications:notification_list', ('notifications',)),
        
        ('Settings', 'admin_staff_portal:preferences', ('settings',)),
        ('Settings > Preferences', 'admin_staff_portal:preferences', ('preferences',)),
        ('Settings > Notification Settings', 'admin_staff_portal:notification_settings', ('notification settings',)),
        ('Settings > Accounts and Security', 'admin_staff_portal:account_and_security', ('accounts and security',)),
        
        ('Profile', 'admin_staff_portal:profile', ('profile',))
    ),
    
    'faculty': (
        ('Dashboard', 'faculty_portal:dashboard', ('dashboard',)),
        
        ('My Documents', 'faculty_portal:my_documents', ('my documents', 'documents')),
        ('All Documents', 'faculty_portal:all_documents', ('all documents',)),
        ('Pinned Documents', 'faculty_portal:pinned_documents', ('pinned documents', 'pinned')),
        
        ('Submission Bin', 'faculty_portal:upload_files', ('submission bin', 'submissions')),
        ('Submission Bin > Upload Files', 'faculty_portal:upload_files', ('submission bin', 'submissions')),
        
        ('My Submissions', 'faculty_portal:my_submissions', ('my submissions',)),
        
        ('Notifications', 'notifications:notification_list', ('notifications',)),
        
        ('Settings', 'faculty_portal:preferences', ('settings',)),
        ('Settings > Preferences', 'faculty_portal:preferences', ('preferences',)),
        ('Settings > Notification Settings', 'faculty_portal:notification_settings', ('notification settings',)),
        ('Settings > Notification Channels', 'faculty_portal:notification_channel', ('notification channels',)),
        ('Settings > Accounts and Security', 'faculty_portal:account_and_security', ('accounts and security',)),
        
        ('Profile', 'faculty_portal:profile', ('profile',))
    )
}


def _portal_key(user):
    return {
        'ADMIN': 'admin',
        'STAFF': 'staff',
        'FACULTY': 'faculty'
    }[user.role]


def _visible_requirements(user):
    if user.is_faculty:
        submitted_requirement_ids = (
            DocumentSubmission.objects
            .filter(faculty=user, requirement_id__isnull=False)
            .exclude(status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION)
            .values_list('requirement_id', flat=True)
        )

        return (
            get_faculty_assigned_requirements(user)
            .filter(deadline__gt=timezone.now())
            .exclude(id__in=submitted_requirement_ids)
        )

    return Requirement.objects.all()


def _visible_documents(user):
    documents = DocumentSubmission.objects.select_related(
        'requirement',
        'faculty',
    ).filter(
        requirement__requirement_title__isnull=False,
    )

    if user.is_faculty:
        return documents.filter(
            faculty=user,
            is_archived=False,
        )

    if user.is_admin:
        return documents.filter(
            Q(is_archived=False)
            | Q(
                is_archived=True,
                status=DocumentSubmission.SubmissionStatus.APPROVED,
            )
        )

    return documents.filter(is_archived=False)


def _navigation_results(user, query):
    terms = query.casefold().split()
    results = []

    for label, route_name, keywords in _NAVIGATION[_portal_key(user)]:
        searchable = f'{label} {" ".join(keywords)}'.casefold()
        if all(term in searchable for term in terms):
            results.append({
                'label': label,
                'category': 'Pages',
                'url': reverse(route_name)
            })

    return results


def _document_navigation_target(user, document):
    is_approved = (document.status == DocumentSubmission.SubmissionStatus.APPROVED)

    if user.is_faculty:
        return (
            ('faculty_portal:all_documents', 'My Documents')
            if is_approved
            else ('faculty_portal:my_submissions', 'My Submissions')
        )

    return (
        ('admin_staff_portal:document_repo', 'Document Repository')
        if is_approved
        else ('admin_staff_portal:faculty_submissions_list', 'Faculty Submissions')
    )


def _document_search_result(user, document):
    route_name, category = _document_navigation_target(user, document)

    title = (
        document.requirement.requirement_title
        if document.requirement_id and document.requirement.requirement_title
        else 'Untitled Document'
    )

    faculty = document.faculty

    faculty_name = (
        ' '.join(
            part.strip()
            for part in (
                faculty.first_name,
                faculty.middle_name,
                faculty.last_name
            )
            if part and part.strip()
        )
        if faculty else ''
    )

    if not faculty_name and faculty:
        faculty_name = faculty.email or faculty.get_username()

    faculty_url = ''

    if faculty and user.role in ('ADMIN', 'STAFF'):
        faculty_search_term = (faculty_name or faculty.email or faculty.get_username())

        faculty_url = (
            f'{reverse("admin_staff_portal:user_list")}?'
            f'{urlencode({
                "role": "FACULTY",
                "q": faculty_search_term,
            })}'
        )

    return {
        'id': document.id,
        'label': title,
        'faculty_name': faculty_name or 'Unknown Faculty',
        'faculty_url': faculty_url,
        'category': category,
        'url': f'{reverse(route_name)}?{urlencode({"q": title})}'
    }


def _faculty_search_results(user, query, limit=None):
    if user.role not in ('ADMIN', 'STAFF') or not query:
        return []

    faculty_queryset = (
        User.objects
        .filter(role=User.Role.FACULTY)
        .filter(
            all_terms_query(
                query,
                'first_name',
                'middle_name',
                'last_name',
                'email'
            )
        )
        .order_by('last_name', 'first_name', 'pk')
    )

    if limit is not None:
        faculty_queryset = faculty_queryset[:limit]

    results = []

    for faculty in faculty_queryset:
        faculty_name = ' '.join(
            part.strip()
            for part in (
                faculty.first_name,
                faculty.middle_name,
                faculty.last_name
            )
            if part and part.strip()
        )

        if not faculty_name:
            faculty_name = faculty.email or faculty.get_username()

        faculty_url = (
            f'{reverse("admin_staff_portal:user_list")}?'
            f'{urlencode({
                "role": User.Role.FACULTY,
                "q": faculty_name
            })}'
        )

        results.append({
            'label': faculty_name,
            'category': 'Faculty',
            'url': faculty_url
        })

    return results


def search_portal(user, query='', limit=None, faculty_name='', document_title=''):
    query = ' '.join((query or '').split())
    faculty_name = ' '.join((faculty_name or '').split())
    document_title = ' '.join((document_title or '').split())
    
    if not any((query, faculty_name, document_title)):
        return {
            'pages': [],
            'faculty': [],
            'requirements': [],
            'documents': []
        }

    is_admin_staff = user.role in ('ADMIN', 'STAFF')

    # Page Search
    pages = (_navigation_results(user, query) if query else [])
    
    if limit is not None:
        pages = pages[:limit]
    
    # Faculty Search
    faculty = _faculty_search_results(user, query, limit=limit)

    # Requirement Search
    requirements = []

    if query:
        requirement_queryset = _visible_requirements(user).filter(all_terms_query(query, 'requirement_title'))

        requirement_url_name = (
            'faculty_portal:upload_files'
            if user.is_faculty
            else 'admin_staff_portal:requirements_list'
        )

        requirement_results = requirement_queryset.order_by('-updated_at', 'requirement_title').values('id', 'requirement_title')

        if limit is not None:
            requirement_results = requirement_results[:limit]

        requirements = [
            {
                'id': item['id'],
                'label': item['requirement_title'],
                'category': 'Requirements',
                'url': (
                    f'{reverse(requirement_url_name)}?'
                    f'{urlencode({"q": item["requirement_title"]})}'
                )
            }
            for item in requirement_results
        ]

    # Document Search
    documents = []

    has_document_search = bool(query) or (is_admin_staff and bool(faculty_name or document_title))

    if has_document_search:
        document_filters = []

        # General search: requirement title or faculty name
        if query:
            general_query = all_terms_query(query, 'requirement__requirement_title')

            if is_admin_staff:
                general_query |= all_terms_query(query, *FACULTY_SEARCH_FIELDS)

            document_filters.append(general_query)

        if is_admin_staff:
            # Advanced faculty name search
            if faculty_name:
                document_filters.append(all_terms_query(faculty_name, *FACULTY_SEARCH_FIELDS))

            # Advanced document title search
            if document_title:
                document_filters.append(all_terms_query(document_title, 'requirement__requirement_title',))

        document_queryset = _visible_documents(user).filter(
            *document_filters
        ).order_by(
            '-initially_submitted_at',
            'requirement__requirement_title'
        )

        if limit is not None:
            document_queryset = document_queryset[:limit]

        documents = [_document_search_result(user, document) for document in document_queryset]
        
    return {
        'pages': pages,
        'faculty': faculty,
        'requirements': requirements,
        'documents': documents
    }