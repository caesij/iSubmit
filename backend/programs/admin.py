from django.contrib import admin

from programs.models import Program

# Program Management for Superuser
@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = (
        'program_name',
        'short_name',
        'created_at',
        'updated_at',
    )

    search_fields = (
        'program_name',
        'short_name',
    )

    ordering = ('program_name',)

    readonly_fields = (
        'created_at',
        'updated_at',
    )