def seed_requirement_templates(sender, using, **kwargs):
    from submissions.models import RequirementTemplate

    Unit = RequirementTemplate.Unit
    AppliesTo = RequirementTemplate.AppliesTo

    SECTION = Unit.PER_SECTION
    YEAR = Unit.PER_YEAR_LEVEL
    FACULTY = Unit.PER_FACULTY

    ALL = AppliesTo.ALL
    REGULAR = AppliesTo.REGULAR
    OJT = AppliesTo.OJT
    LAB = AppliesTo.LAB

    default_requirements = [
        ("Class Record", SECTION, ALL, True),
        ("Gradesheets", SECTION, ALL, True),
        ("Midterm Exam", YEAR, REGULAR, True),
        ("Midterm Exam with Answer", SECTION, REGULAR, False),
        ("Final Exam", YEAR, REGULAR, True),
        ("Final Exam with Answer", SECTION, REGULAR, False),
        ("Table of Specifications (TOS) - Midterm Examination", YEAR, REGULAR, True),
        ("Table of Specifications (TOS) - Final Examination", YEAR, REGULAR, True),
        ("Test Item Analysis (TIA) - Midterm Examination", YEAR, REGULAR, True),
        ("Test Item Analysis (TIA) - Final Examination", YEAR, REGULAR, True),
        ("Syllabus", YEAR, ALL, True),
        ("Instructional Materials (IM)", YEAR, REGULAR, True),
        ("OJT Evaluation Summary Report", YEAR, OJT, True),
        ("OJT Monitoring Sheet", YEAR, OJT, True),
        ("OJT Portfolio", YEAR, OJT, True),
        ("Laboratory Manual", YEAR, LAB, True),
        ("Rubrics", YEAR, ALL, True),
        ("Workplan", YEAR, ALL, True),
        ("PDS/CV", FACULTY, ALL, True),
    ]

    templates = [
        RequirementTemplate(
            requirement_title=title,
            unit=unit,
            applies_to=applies_to,
            is_required=is_required,
            order=position,
        )
        for position, (title, unit, applies_to, is_required)
        in enumerate(default_requirements, start=1)
    ]

    RequirementTemplate.objects.using(using).bulk_create(templates, ignore_conflicts=True,)
