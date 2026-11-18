from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models


class Program(models.Model):
    program_name = models.CharField(max_length=150, unique=True)
    short_name = models.CharField(max_length=20, unique=True)

    duration_years = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )

    courses = models.ManyToManyField(
        'submissions.Course',
        through='ProgramCourse',
        related_name='programs',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['program_name']

    def __str__(self):
        return f'{self.short_name} - {self.program_name}'


class ProgramSection(models.Model):
    academic_year = models.CharField(
        max_length=9,
        validators=[
            RegexValidator(
                r'^\d{4}-\d{4}$',
                'Use the format 2023-2024.',
            )
        ],
    )

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='sections')
    year_level = models.PositiveSmallIntegerField()
    section = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)],)

    class Meta:
        ordering = ['-academic_year', 'year_level', 'section']

        constraints = [
            models.UniqueConstraint(
                fields=[
                    'program',
                    'academic_year',
                    'year_level',
                    'section'
                ],
                name='unique_program_ay_year_section'
            )
        ]

    def clean(self):
        super().clean()

        if self.program_id and self.year_level:
            if self.year_level > self.program.duration_years:
                raise ValidationError({'year_level': ('This program does not have that year level.')})

    def __str__(self):
        return (
            f'{self.program.short_name} '
            f'{self.year_level}-{self.section} '
            f'({self.academic_year})'
        )


class ProgramCourse(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='program_courses')

    course = models.ForeignKey('submissions.Course', on_delete=models.PROTECT, related_name='program_links')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['course__code']
        constraints = [
            models.UniqueConstraint(
                fields=['program', 'course'],
                name='unique_course_per_program'
            )
        ]

    def __str__(self):
        return f'{self.program.short_name} - {self.course.code}'
