from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import UserManager, FacultyManager, StaffManager

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", 'Admin'
        STAFF = "STAFF", 'Staff'
        FACULTY = "FACULTY", 'Faculty'

    class FacultyType(models.TextChoices):
        FULL_TIME = "FULL_TIME", 'Full-Time Faculty'
        PART_TIME = "PART_TIME", 'Part-Time Faculty'
        N_A = "N/A", 'N/A' # Default for Staff/Admins

    class InvitationStatus(models.TextChoices):
        ACTIVATED = "ACTIVATED", 'Activated'
        SENT = "SENT", 'Invitation Sent'
        PENDING = "PENDING", 'Pending'

    # Core Fields
    email = models.EmailField(
        unique=True, 
        error_messages={
            'unique': 'A user with this email already exists.'
        }
    )

    title = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="e.g., Asst. Prof., Dr."
    )

    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255)

    faculty_type = models.CharField(
        max_length=100,
        choices=FacultyType.choices,
        default=FacultyType.N_A
    )

    invitation_status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING
    )

    # Permission Fields
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.FACULTY)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Tracking Fields
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'middle_name', 'last_name']

    def save(self, *args, **kwargs):
        # Admin
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        # Staff
        elif self.role == self.Role.STAFF:
            self.is_staff = True
            self.is_superuser = False
        # Faculty Member
        else:
            self.is_staff = False
            self.is_superuser = False

        super().save(*args, **kwargs)

    def get_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    def __str__(self):
        return self.get_full_name()

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_staff_role(self):
        return self.role == self.Role.STAFF

    @property
    def is_faculty(self):
        return self.role == self.Role.FACULTY

class FacultyAccount(User):
    objects = FacultyManager()
    class Meta:
        proxy = True
        verbose_name = "Faculty Account"
        verbose_name_plural = "Faculty Accounts"

class StaffAccount(User):
    objects = StaffManager()
    class Meta:
        proxy = True
        verbose_name = "Staff Account"
        verbose_name_plural = "Staff Accounts"