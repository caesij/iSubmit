from django import forms
from programs.models import Program

class ProgramForm(forms.ModelForm):

    class Meta:
        model = Program
        fields = ['program_name', 'short_name']

    def clean_program_name(self):
        program_name = self.cleaned_data['program_name'].strip()

        existing = Program.objects.filter(program_name__iexact=program_name)

        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError('A program with this name already exists.')

        return program_name

    def clean_short_name(self):
        short_name = self.cleaned_data['short_name'].strip()

        existing = Program.objects.filter(short_name__iexact=short_name)

        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError('A program with this acronym/abbreviation already exists.')

        return short_name