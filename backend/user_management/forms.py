from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.contrib.auth import get_user_model

from programs.models import Program, ProgramSection
from submissions.models import ClassAssignment, Course, SubmissionPeriod


User = get_user_model()


class UserManagementForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=User.Role.choices
    )

    faculty_type = forms.ChoiceField(
        choices=User.FacultyType.choices,
        required=False
    )

    assigned_programs = forms.ModelMultipleChoiceField(
        queryset=Program.objects.none(),
        required=False
    )

    is_active = forms.TypedChoiceField(
        choices=[
            ('True', 'Active'),
            ('False', 'Inactive'),
        ],
        coerce=lambda value: value == 'True',
        required=True
    )

    class Meta:
        model = User
        fields = [
            'first_name',
            'middle_name',
            'last_name',
            'employee_ID',
            'email',
            'role',
            'faculty_type',
            'assigned_programs',
            'is_active',
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)

        super().__init__(*args, **kwargs)

        self.fields['assigned_programs'].queryset = (
            Program.objects.order_by('program_name')
        )

        if self.request_user and self.request_user.is_admin:
            self.fields['role'].choices = [
                choice for choice in User.Role.choices
                if choice[0] in [User.Role.STAFF, User.Role.FACULTY]
            ]
        else:
            self.fields['role'].choices = [
                (User.Role.FACULTY, User.Role.FACULTY.label)
            ]

        if not self.instance.pk:
            self.fields['role'].initial = User.Role.FACULTY
            self.fields['is_active'].initial = 'True'

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip().upper()

    def clean_middle_name(self):
        return self.cleaned_data.get('middle_name', '').strip().upper()

    def clean_last_name(self):
        return self.cleaned_data['last_name'].strip().upper()

    def clean_employee_ID(self):
        employee_id = self.cleaned_data['employee_ID'].strip()

        existing = User.objects.filter(
            employee_ID__iexact=employee_id
        ).exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError('This employee ID is already registered.')

        return employee_id

    def clean_email(self):
        email = self.cleaned_data['email'].strip()

        existing = User.objects.filter(
            email__iexact=email
        ).exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError('This email address is already registered.')

        return email

    def clean(self):
        cleaned_data = super().clean()

        role = cleaned_data.get('role')

        if role == User.Role.FACULTY:
            if not cleaned_data.get('faculty_type'):
                self.add_error(
                    'faculty_type',
                    'Select a faculty type.'
                )
        else:
            cleaned_data['faculty_type'] = ''
            cleaned_data['assigned_programs'] = Program.objects.none()

        return cleaned_data


class ClassAssignmentForm(forms.ModelForm):
    academic_year = forms.ChoiceField(
        choices=[],
        required=True
    )

    program_section = forms.ModelChoiceField(
        queryset=ProgramSection.objects.none(),
        required=True,
        label='Section'
    )

    year_level = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )

    section = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = ClassAssignment
        fields = [
            'program',
            'academic_year',
            'semester',
            'course',
            'year_level',
            'section',
        ]

    def __init__(self, *args, **kwargs):
        allowed_programs = kwargs.pop(
            'allowed_programs',
            Program.objects.none()
        )

        super().__init__(*args, **kwargs)

        self.fields['program'].queryset = allowed_programs.order_by(
            'program_name'
        )

        self.fields['course'].queryset = Course.objects.none()
        self.fields['program_section'].queryset = ProgramSection.objects.none()

        self.fields['academic_year'].choices = [
            ('', 'Select an academic year')
        ]

        self.fields['semester'].choices = [
            ('', 'Select a semester')
        ] + list(SubmissionPeriod.Semester.choices)

        # Get the selected program from the submitted form or existing record.
        if self.is_bound:
            program_id = self.data.get(self.add_prefix('program'))
        else:
            program_id = self.initial.get(
                'program',
                self.instance.program_id
            )

        program = allowed_programs.filter(pk=program_id).first()

        if not program:
            return

        # Only show academic years where this program has sections.
        academic_years = sorted(
            set(
                program.sections.values_list(
                    'academic_year',
                    flat=True
                )
            ),
            reverse=True
        )

        self.fields['academic_year'].choices = [
            ('', 'Select an academic year')
        ] + [
            (year, f'A.Y. {year}')
            for year in academic_years
        ]

        # Courses are currently linked to a program, not an academic year.
        self.fields['course'].queryset = program.courses.order_by('code')

        if self.is_bound:
            academic_year = self.data.get(
                self.add_prefix('academic_year')
            )
        else:
            academic_year = self.initial.get(
                'academic_year',
                self.instance.academic_year
            )

        sections = program.sections.filter(
            academic_year=academic_year
        ).order_by('year_level', 'section')

        self.fields['program_section'].queryset = sections

        # Restore the selected section when editing an existing assignment.
        if not self.is_bound and self.instance.pk:
            try:
                section_number = int(self.instance.section)

                selected_section = sections.filter(
                    year_level=self.instance.year_level,
                    section=section_number
                ).first()

                if selected_section:
                    self.initial['program_section'] = selected_section.pk

            except (TypeError, ValueError):
                pass

    def clean(self):
        cleaned_data = super().clean()

        program = cleaned_data.get('program')
        academic_year = cleaned_data.get('academic_year')
        course = cleaned_data.get('course')
        selected_section = cleaned_data.get('program_section')

        if program and academic_year and selected_section and course:
            if (
                selected_section.program_id != program.pk
                or selected_section.academic_year != academic_year
            ):
                self.add_error(
                    'program_section',
                    'The selected section does not match the program and academic year.'
                )
            else:
                # Map ProgramSection values to the existing ClassAssignment fields.
                cleaned_data['year_level'] = selected_section.year_level
                cleaned_data['section'] = str(selected_section.section)

                self.instance.year_level = selected_section.year_level
                self.instance.section = str(selected_section.section)

        return cleaned_data


class BaseClassAssignmentFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        existing_assignments = set()

        for form in self.forms:
            data = form.cleaned_data

            if not data or data.get('DELETE'):
                continue

            program = data.get('program')
            academic_year = data.get('academic_year')
            semester = data.get('semester')
            course = data.get('course')
            selected_section = data.get('program_section')

            if not all([
                program,
                academic_year,
                semester,
                course,
                selected_section,
            ]):
                continue

            assignment_key = (
                program.pk,
                academic_year,
                semester,
                course.pk,
                selected_section.year_level,
                selected_section.section,
            )

            if assignment_key in existing_assignments:
                raise ValidationError(
                    'The same teaching assignment has been added more than once.'
                )

            existing_assignments.add(assignment_key)


ClassAssignmentFormSet = inlineformset_factory(
    User,
    ClassAssignment,
    form=ClassAssignmentForm,
    formset=BaseClassAssignmentFormSet,
    fk_name='faculty',
    extra=1,
    can_delete=True,
)
