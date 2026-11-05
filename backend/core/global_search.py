from functools import reduce
from operator import and_
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from submissions.models import DocumentSubmission, Requirement
from submissions.helpers import get_faculty_assigned_requirements


RESULT_LIMIT = 4

_NAVIGATION = {
    'admin': (
        ('Dashboard', 'admin_staff_portal:admin_dashboard', ('dashboard',)),
        
        ('Documents', 'admin_staff_portal:document_repo', ('documents', 'document repository')),
        ('Document Archive', 'admin_staff_portal:document_archive', ('document archive', 'archive')),
        
        ('Submissions', 'admin_staff_portal:requirements_list', ('submissions', 'submission')),
        ('Submission Bin', 'admin_staff_portal:requirements_list', ('submission bin', 'requirements')),
        ('Faculty Submissions', 'admin_staff_portal:faculty_submissions_list', ('faculty submissions',)),
        
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
        ('Submission Bin', 'admin_staff_portal:requirements_list', ('submission bin', 'requirements')),
        ('Faculty Submissions', 'admin_staff_portal:faculty_submissions_list', ('faculty submissions',)),
        
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


def _matching_terms(query):
    return tuple(part for part in query.split() if part)


def _title_query(terms, field='requirement_title'):
    return reduce(and_, (Q(**{f'{field}__icontains': term}) for term in terms))


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
    title = document.requirement.requirement_title

    return {
        'id': document.id,
        'label': title,
        'category': category,
        'url': f'{reverse(route_name)}?{urlencode({"q": title})}',
    }

def search_portal(user, query, limit=None):
    query = ' '.join((query or '').split())
    if not query:
        return {'pages': [], 'requirements': [], 'documents': []}

    terms = _matching_terms(query)
    
    requirement_queryset = (
        _visible_requirements(user)
        .filter(_title_query(terms))
        .order_by('-updated_at', 'requirement_title')
    )
    
    requirement_url_name = (
        'faculty_portal:upload_files'
        if user.is_faculty
        else 'admin_staff_portal:requirements_list'
    )
    
    requirement_results = requirement_queryset.values('id', 'requirement_title')
    
    document_queryset = (
        _visible_documents(user)
        .filter(_title_query(terms, 'requirement__requirement_title'))
        .order_by('-initially_submitted_at', 'requirement__requirement_title')
    )
    
    if limit is not None:
        requirement_results = requirement_results[:limit]
        document_queryset = document_queryset[:limit]

    return {
        'pages': _navigation_results(user, query),
        
        'requirements': [
            {
                'id': item['id'],
                'label': item['requirement_title'],
                'category': 'Requirements',
                'url': (f'{reverse(requirement_url_name)}?{urlencode({"q": item["requirement_title"]})}')
            }
            for item in requirement_results
        ],
        
        'documents': [
            _document_search_result(user, document)
            for document in document_queryset
        ]
    }
