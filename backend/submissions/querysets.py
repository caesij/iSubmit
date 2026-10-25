from submissions.models import DocumentSubmission

def active_document_queryset(queryset=None):
    if queryset is None:
        queryset = DocumentSubmission.objects
    return queryset.filter(is_archived=False)
