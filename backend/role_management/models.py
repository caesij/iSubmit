from django.contrib.auth.models import Group
from django.db import models


class Role(models.Model):
    class Code(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        STAFF = 'STAFF', 'Staff'
        FACULTY = 'FACULTY', 'Faculty'

    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='managed_role',
    )
    code = models.CharField(
        max_length=20,
        choices=Code.choices,
        unique=True,
        null=True,
        blank=True,
    )
    is_default = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-is_default', 'group__name')

    def __str__(self):
        return self.group.name

    @property
    def is_faculty_role(self):
        return self.code == self.Code.FACULTY

    @property
    def is_admin_role(self):
        return self.code == self.Code.ADMIN

    @property
    def is_staff_role(self):
        return self.code == self.Code.STAFF


class RoleUserManagementRule(models.Model):
    manager_role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_management_rules',
    )
    
    target_role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='managed_by_rules'
    )
    
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_change_status = models.BooleanField(default=False)
    can_unlock = models.BooleanField(default=False)

    class Meta:
        ordering = ('target_role__group__name',)
        constraints = [
            models.UniqueConstraint(
                fields=('manager_role', 'target_role'),
                name='unique_role_user_management_rule'
            ),
        ]

    def __str__(self):
        return (f'{self.manager_role.group.name} -> {self.target_role.group.name}')
