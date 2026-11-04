from django.db import models

class Program(models.Model):
    program_name = models.CharField(
        max_length=150,
        unique=True,
    )

    short_name = models.CharField(
        max_length=20,
        unique=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['program_name']

    def __str__(self):
        return f'{self.short_name} - {self.program_name}'