from django.core.management.base import BaseCommand

from submissions.models import RequirementTemplate

Unit = RequirementTemplate.Unit
AppliesTo = RequirementTemplate.AppliesTo

SECTION, YEAR, FACULTY = Unit.PER_SECTION, Unit.PER_YEAR_LEVEL, Unit.PER_FACULTY
ALL, REGULAR, OJT, LAB = AppliesTo.ALL, AppliesTo.REGULAR, AppliesTo.OJT, AppliesTo.LAB

# (title, uploads owed, applies to, is required). The order here is the order shown on the checklist.
# "One per course and year level" means the sections of one year level share a single upload.
DEFAULT_REQUIREMENTS = [
    ('Class Record', SECTION, ALL, True),
    ('Gradesheets', SECTION, ALL, True),
    ('Midterm Exam', YEAR, REGULAR, True),
    ('Midterm Exam with Answer', SECTION, REGULAR, False),
    ('Final Exam', YEAR, REGULAR, True),
    ('Final Exam with Answer', SECTION, REGULAR, False),
    ('Table of Specifications (TOS) - Midterm Examination', YEAR, REGULAR, True),
    ('Table of Specifications (TOS) - Final Examination', YEAR, REGULAR, True),
    ('Test Item Analysis (TIA) - Midterm Examination', YEAR, REGULAR, True),
    ('Test Item Analysis (TIA) - Final Examination', YEAR, REGULAR, True),
    ('Syllabus', YEAR, ALL, True),
    ('Instructional Materials (IM)', YEAR, REGULAR, True),
    ('OJT Evaluation Summary Report', YEAR, OJT, True),
    ('OJT Monitoring Sheet', YEAR, OJT, True),
    ('OJT Portfolio', YEAR, OJT, True),
    ('Laboratory Manual', YEAR, LAB, True),
    ('Rubrics', YEAR, ALL, True),
    ('Workplan', YEAR, ALL, True),
    ('PDS/CV', FACULTY, ALL, True),
]


class Command(BaseCommand):
    help = 'Adds the default requirement checklist. Safe to run again: existing items are left untouched.'

    def handle(self, *args, **options):
        templates = [
            RequirementTemplate(
                requirement_title=title, unit=unit, applies_to=applies_to, is_required=is_required, order=position
            )
            for position, (title, unit, applies_to, is_required) in enumerate(DEFAULT_REQUIREMENTS, start=1)
        ]
        RequirementTemplate.objects.bulk_create(templates, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f'Default checklist ready ({RequirementTemplate.objects.count()} items).'))
