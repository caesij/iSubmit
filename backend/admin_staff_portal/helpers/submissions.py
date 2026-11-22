from submissions.models import DocumentSubmission, active_q

def get_active_submissions():
    return DocumentSubmission.objects.filter(active_q('requirement__'))
