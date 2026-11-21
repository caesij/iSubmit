ROLE_GROUP_NAMES = {
    'ADMIN': 'Admin',
    'STAFF': 'Staff',
    'FACULTY': 'Faculty',
}


ALL_ROLE_CODES = frozenset(ROLE_GROUP_NAMES)


COMMON_DEFAULT_PERMISSION_CODES = (
    'access_preferences',
    'access_notification_settings',
    'access_account_security',
    'access_profile',
)


PERMISSION_PAGES = (
    {
        'key': 'admin_dashboard',
        'title': 'Admin Dashboard',
        'description': 'Access the administrative dashboard.',
        'access_codename': 'access_admin_dashboard',
        'available_to': frozenset({'ADMIN'}),
        'operations': (),
    },
    {
        'key': 'staff_dashboard',
        'title': 'Staff Dashboard',
        'description': 'Access the staff dashboard.',
        'access_codename': 'access_staff_dashboard',
        'available_to': frozenset({'STAFF'}),
        'operations': (),
    },
    {
        'key': 'faculty_dashboard',
        'title': 'Faculty Dashboard',
        'description': 'Access the faculty dashboard.',
        'access_codename': 'access_faculty_dashboard',
        'available_to': frozenset({'FACULTY'}),
        'operations': (),
    },
    {
        'key': 'user_management',
        'title': 'User Management',
        'description': 'Manage user accounts and their account status.',
        'access_codename': 'access_user_management',
        'available_to': frozenset({'ADMIN', 'STAFF'}),
        'operations': (
            {
                'codename': 'add_users',
                'label': 'Add Users',
                'description': 'Create manageable user accounts.',
            },
            {
                'codename': 'edit_users',
                'label': 'Edit Users',
                'description': 'Edit manageable user accounts.',
            },
            {
                'codename': 'manage_all_users',
                'label': 'Manage All Users',
                'description': 'View and manage accounts across all assigned Roles.',
            },
            {
                'codename': 'manage_faculty_users',
                'label': 'Manage Faculty Users',
                'description': 'View and manage accounts assigned the built-in Faculty Role.',
            },
            {
                'codename': 'toggle_user_status',
                'label': 'Activate or Deactivate Users',
                'description': 'Change the active status of manageable accounts.',
            },
            {
                'codename': 'unlock_user_accounts',
                'label': 'Unlock User Accounts',
                'description': 'Release locked user accounts.',
            },
        ),
    },
    {
        'key': 'program_management',
        'title': 'Program Management',
        'description': 'Manage programs, sections, and courses.',
        'access_codename': 'access_program_management',
        'available_to': frozenset({'ADMIN', 'STAFF'}),
        'operations': (
            {
                'codename': 'manage_programs',
                'label': 'Manage Programs and Courses',
                'description': 'Create, edit, and remove programs, sections, and courses.',
            },
        ),
    },
    {
        'key': 'submission_requirements',
        'title': 'Submission Requirements',
        'description': 'Manage submission periods and their requirements.',
        'access_codename': 'access_submission_requirements',
        'available_to': frozenset({'ADMIN', 'STAFF'}),
        'operations': (
            {
                'codename': 'manage_submission_bins',
                'label': 'Manage Submission Requirements',
                'description': 'Create and edit submission periods and requirements.',
            },
        ),
    },
    {
        'key': 'faculty_submissions',
        'title': 'Faculty Submissions',
        'description': 'View and process submitted faculty documents.',
        'access_codename': 'access_faculty_submissions',
        'available_to': frozenset({'ADMIN', 'STAFF'}),
        'operations': (
            {
                'codename': 'review_faculty_submissions',
                'label': 'Review Faculty Submissions',
                'description': 'Move submissions through the review process.',
            },
            {
                'codename': 'return_for_revisions',
                'label': 'Return for Revisions',
                'description': 'Return a submission with remarks.',
                'requires': ('review_faculty_submissions',),
            },
            {
                'codename': 'approve_submissions',
                'label': 'Approve Submissions',
                'description': 'Approve eligible faculty submissions.',
            },
        ),
    },
    {
        'key': 'document_repository',
        'title': 'Document Repository',
        'description': 'View approved documents in the repository.',
        'access_codename': 'access_document_repository',
        'available_to': frozenset({'ADMIN', 'STAFF'}),
        'operations': (),
    },
    {
        'key': 'document_archive',
        'title': 'Document Archive',
        'description': 'View and manage archived documents.',
        'access_codename': 'access_document_archive',
        'available_to': frozenset({'ADMIN'}),
        'operations': (
            {
                'codename': 'manage_document_archive',
                'label': 'Manage Document Archive',
                'description': 'Archive, restore, and permanently delete approved documents.',
            },
        ),
    },
    {
        'key': 'faculty_submission_bin',
        'title': 'Faculty Submission Bin',
        'description': 'Access assigned submission requirements and uploaded files.',
        'access_codename': 'access_faculty_submission_bin',
        'available_to': frozenset({'FACULTY'}),
        'operations': (
            {
                'codename': 'upload_documents',
                'label': 'Upload Documents',
                'description': 'Upload documents to assigned requirements.',
            },
            {
                'codename': 'submit_documents',
                'label': 'Submit Documents',
                'description': 'Submit completed documents for review.',
            },
            {
                'codename': 'replace_documents',
                'label': 'Replace Documents',
                'description': 'Replace an uploaded document.',
            },
            {
                'codename': 'remove_documents',
                'label': 'Remove Documents',
                'description': 'Remove an uploaded document.',
            },
            {
                'codename': 'retry_document_extraction',
                'label': 'Retry Text Extraction',
                'description': 'Retry extraction for an uploaded document.',
            },
            {
                'codename': 'resubmit_documents',
                'label': 'Prepare Revision Uploads',
                'description': 'Prepare replacement uploads for returned submissions.',
            },
        ),
    },
    {
        'key': 'my_submissions',
        'title': 'My Submissions',
        'description': 'View personal submission records.',
        'access_codename': 'access_my_submissions',
        'available_to': frozenset({'FACULTY'}),
        'operations': (),
    },
    {
        'key': 'my_documents',
        'title': 'My Documents',
        'description': 'View approved and pinned documents.',
        'access_codename': 'access_my_documents',
        'available_to': frozenset({'FACULTY'}),
        'operations': (
            {
                'codename': 'toggle_document_pin',
                'label': 'Pin or Unpin Documents',
                'description': 'Add or remove documents from the pinned list.',
            },
        ),
    },
    {
        'key': 'preferences',
        'title': 'Preferences',
        'description': 'View and update personal preferences.',
        'access_codename': 'access_preferences',
        'available_to': ALL_ROLE_CODES,
        'operations': (),
    },
    {
        'key': 'notification_settings',
        'title': 'Notification Settings',
        'description': 'View and update notification preferences.',
        'access_codename': 'access_notification_settings',
        'available_to': ALL_ROLE_CODES,
        'operations': (),
    },
    {
        'key': 'account_security',
        'title': 'Account & Security',
        'description': 'Manage account security settings.',
        'access_codename': 'access_account_security',
        'available_to': ALL_ROLE_CODES,
        'operations': (),
    },
    {
        'key': 'profile',
        'title': 'Profile',
        'description': 'View and update account profile information.',
        'access_codename': 'access_profile',
        'available_to': ALL_ROLE_CODES,
        'operations': (),
    },
)


PAGE_PERMISSION_CODES = tuple(page['access_codename'] for page in PERMISSION_PAGES)


OPERATION_PARENT_PAGES = {
    operation['codename']: page['access_codename']
    for page in PERMISSION_PAGES
    for operation in page['operations']
}


OPERATION_PERMISSION_CODES = tuple(OPERATION_PARENT_PAGES)


ALL_PERMISSION_CODES = tuple(dict.fromkeys(PAGE_PERMISSION_CODES + OPERATION_PERMISSION_CODES))


PERMISSION_DETAILS = {page['access_codename']: (page['title'], page['description']) for page in PERMISSION_PAGES}


PERMISSION_DETAILS.update({
    operation['codename']: (operation['label'], operation['description'])
    for page in PERMISSION_PAGES
    for operation in page['operations']
})


DEFAULT_ROLE_PERMISSIONS = {
    'ADMIN': ALL_PERMISSION_CODES,

    'STAFF': (
        'access_staff_dashboard',

        'access_user_management',
        'add_users',
        'edit_users',
        'toggle_user_status',
        'manage_faculty_users',

        'access_program_management',
        'manage_programs',

        'access_submission_requirements',
        'manage_submission_bins',

        'access_faculty_submissions',
        'review_faculty_submissions',
        'return_for_revisions',

        'access_document_repository',

        'access_preferences',
        'access_notification_settings',
        'access_account_security',
        'access_profile'
    ),
    
    'FACULTY': (
        'access_faculty_dashboard',

        'access_faculty_submission_bin',
        'upload_documents',
        'submit_documents',
        'replace_documents',
        'remove_documents',
        'retry_document_extraction',
        'resubmit_documents',

        'access_my_submissions',

        'access_my_documents',
        'toggle_document_pin',

        'access_preferences',
        'access_notification_settings',
        'access_account_security',
        'access_profile'
    ),
}


PERMISSION_SECTIONS = (
    (
        'Page Access',
        tuple(
            (
                page['access_codename'],
                page['title'],
                page['description'],
            )
            for page in PERMISSION_PAGES
        ),
    ),
    (
        'Operations',
        tuple(
            (
                operation['codename'],
                operation['label'],
                operation['description'],
            )
            for page in PERMISSION_PAGES
            for operation in page['operations']
        ),
    ),
)
