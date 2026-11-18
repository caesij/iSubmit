from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from programs.models import Program, ProgramSection, ProgramCourse
from submissions.models import Course, ClassAssignment


def current_academic_year():
    today = timezone.localdate()
    start = today.year if today.month >= 6 else today.year - 1

    return f'{start}-{start + 1}'


def academic_year_choices(program=None):
    current_start = int(current_academic_year().split('-')[0])

    years = {
        f'{year}-{year + 1}'
        for year in range(current_start - 5, current_start + 6)
    }

    if program:
        years.update(section.academic_year for section in program.sections.all())

    return [(year, year) for year in sorted(years, reverse=True)]


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = [
            'program_name',
            'short_name',
            'duration_years'
        ]

        widgets = {
            'program_name': forms.TextInput(
                attrs={'placeholder': 'Program name'}
            ),
            'short_name': forms.TextInput(
                attrs={'placeholder': 'e.g. BSIT'}
            ),
            'duration_years': forms.NumberInput(
                attrs={'min': 1, 'max': 10}
            )
        }

    def clean_program_name(self):
        return ' '.join(self.cleaned_data['program_name'].split())

    def clean_short_name(self):
        return self.cleaned_data['short_name'].strip().upper()

    def clean_duration_years(self):
        years = self.cleaned_data['duration_years']

        if not self.instance.pk:
            return years

        # Do not reduce the duration below existing sections
        if self.instance.sections.filter(
            year_level__gt=years
        ).exists():
            raise ValidationError(
                'The duration cannot be reduced because sections already exist beyond this year level.'
            )

        # Also preserve existing faculty assignments
        if ClassAssignment.objects.filter(
            program=self.instance,
            year_level__gt=years,
        ).exists():
            raise ValidationError(
                'The duration cannot be reduced because faculty assignments exist beyond this year level.'
            )

        return years


class ProgramSectionForm(forms.ModelForm):
    class Meta:
        model = ProgramSection
        fields = [
            'academic_year',
            'year_level',
            'section',
        ]

        widgets = {
            'section': forms.NumberInput(
                attrs={
                    'min': 1,
                    'placeholder': 'Section number',
                }
            ),
        }

    def __init__(self, *args, program=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.program = program or getattr(self.instance, 'program', None)

        current_year = current_academic_year()

        self.fields['academic_year'] = forms.ChoiceField(
            choices=academic_year_choices(self.program),
            label='Academic Year'
        )

        if not self.is_bound:
            self.fields['academic_year'].initial = (
                self.initial.get('academic_year')
                or (
                    self.instance.academic_year
                    if self.instance.pk
                    else current_academic_year()
                )
            )


class ProgramCourseForm(forms.ModelForm):
    class Meta:
        model = ProgramCourse
        fields = ['course']

    def __init__(self, *args, program=None, **kwargs):
        super().__init__(*args, **kwargs)

        if program:
            self.fields['course'].queryset = (
                Course.objects
                .exclude(program_links__program=program)
                .order_by('code')
            )


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'code',
            'title',
            'is_ojt',
            'has_lab'
        ]

        labels = {
            'code': 'Course Code',
            'title': 'Course Title',
            'is_ojt': 'OJT / Practicum Course',
            'has_lab': 'Has Laboratory'
        }

        widgets = {
            'code': forms.TextInput(
                attrs={'placeholder': 'e.g. IT101'}
            ),
            'title': forms.TextInput(
                attrs={'placeholder': 'Course title'}
            )
        }

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()

    def clean_title(self):
        return ' '.join(self.cleaned_data['title'].split())
