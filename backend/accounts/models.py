import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

from .managers import UserManager, FacultyManager, StaffManager

def profile_photo_path(instance, filename):
    return f'profile_photos/user_{instance.id}/{filename}'

class User(AbstractBaseUser, PermissionsMixin):
    # User Preferences
    class DateFormatChoice(models.TextChoices):
        LONG = 'F j, Y', 'Month DD, YYYY (June 1, 2026)'
        SHORT = 'm/d/Y', 'MM/DD/YYYY'
        ISO = 'Y-m-d', 'YYYY-MM-DD'

    class TimeFormatChoice(models.TextChoices):
        TWELVE = '12', '12-hour (AM/PM)'
        TWENTY_FOUR = '24', '24-hour'
    
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='Asia/Manila')
    
    date_format = models.CharField(
        max_length=10, 
        choices=DateFormatChoice.choices, 
        default=DateFormatChoice.LONG
    )
    
    time_format = models.CharField(
        max_length=2, 
        choices=TimeFormatChoice.choices, 
        default=TimeFormatChoice.TWELVE
    )
    
    # Main User Creation
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    class Role(models.TextChoices):
        ADMIN = "ADMIN", 'Admin'
        STAFF = "STAFF", 'Staff'
        FACULTY = "FACULTY", 'Faculty'

    class FacultyType(models.TextChoices):
        FULL_TIME = "FULL_TIME", 'Full-Time Faculty'
        PART_TIME = "PART_TIME", 'Part-Time Faculty'
        
    profile_photo = models.ImageField(
        upload_to=profile_photo_path,
        blank=True,
        null=True,
    )
    
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255)

    employee_ID = models.CharField(
        max_length=50,
        unique=True,
        error_messages={
            'unique': 'A user with this employee ID already exists.'
        },
    )

    email = models.EmailField(
        unique=True, 
        error_messages={
            'unique': 'A user with this email already exists.'
        },
    )

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.FACULTY)

    faculty_type = models.CharField(
        max_length=20, 
        choices=FacultyType.choices,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    is_locked_out = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'middle_name', 'last_name', 'employee_ID']

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

    def get_short_name(self):
        return self.email.split('@')[0]

    def __str__(self):
        return self.get_short_name()

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

class StaffPermission(models.Model):
    review_faculty_submissions = models.BooleanField(default=True)
    return_for_revisions = models.BooleanField(default=True)
    create_submission_bins = models.BooleanField(default=True)
    edit_submission_bin = models.BooleanField(default=True)
    view_approved_documents = models.BooleanField(default=True)
    add_faculty_users = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    DEPENDENCIES = {
        'return_for_revisions': ['review_faculty_submissions'],
    }
    
    class Meta:
        verbose_name = 'Staff Permission'
        verbose_name_plural = 'Staff Permissions'

    def __str__(self):
        return 'Staff Permissions'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def is_effectively_enabled(self, field):
        if not getattr(self, field, False):
            return False
        for dependency in self.DEPENDENCIES.get(field, []):
            if not getattr(self, dependency, False):
                return False
        return True

    def enforce_dependencies(self):
        for field, dependencies in self.DEPENDENCIES.items():
            if any(not getattr(self, dep, False) for dep in dependencies):
                setattr(self, field, False)

    def save(self, *args, **kwargs):
        self.pk = 1
        self.enforce_dependencies()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass
     
class NotificationPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    class NotificationType(models.TextChoices):
        SYSTEM_ANNOUNCEMENT = 'SYSTEM_ANNOUNCEMENT', 'System Announcement'
        DOCUMENT_UPDATES = 'DOCUMENT_UPDATES', 'Document Updates'
        SUBMISSION_UPDATES = 'SUBMISSION_UPDATES', 'Submission Updates'
        SUBMISSION_REMINDERS = 'SUBMISSION_REMINDERS', 'Submission Reminders'
        APPROVAL_REJECTIONS = 'APPROVAL_REJECTIONS', 'Approval and Rejections'
        SECURITY_ALERTS = 'SECURITY_ALERTS', 'Security Alerts'

    DESCRIPTIONS = {
        NotificationType.SYSTEM_ANNOUNCEMENT: 'Receive alerts about important system announcement and updates.',
        NotificationType.DOCUMENT_UPDATES: 'Updates about your submitted documents.',
        NotificationType.SUBMISSION_UPDATES: 'Get notified on submissions status.',
        NotificationType.SUBMISSION_REMINDERS: 'Reminders for pending submission and deadlines.',
        NotificationType.APPROVAL_REJECTIONS: 'Notifications about documents approvals or rejections.',
        NotificationType.SECURITY_ALERTS: 'Login alerts and security-related notifications.',
    }

    ROLE_TYPES = {
        'FACULTY': [
            NotificationType.SYSTEM_ANNOUNCEMENT,
            NotificationType.DOCUMENT_UPDATES,
            NotificationType.SUBMISSION_REMINDERS,
            NotificationType.APPROVAL_REJECTIONS,
            NotificationType.SECURITY_ALERTS,
        ],
        'ADMIN': [
            NotificationType.SYSTEM_ANNOUNCEMENT,
            NotificationType.SUBMISSION_UPDATES,
            NotificationType.SECURITY_ALERTS,
        ],
        'STAFF': [
            NotificationType.SYSTEM_ANNOUNCEMENT,
            NotificationType.SUBMISSION_UPDATES,
            NotificationType.SECURITY_ALERTS,
        ],
    }
    
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
    )

    enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    system_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'notification_type'],
                name='unique_user_notification_type'
            )
        ]

    @property
    def description(self):
        return self.DESCRIPTIONS.get(self.notification_type, '')

    def __str__(self):
        return f'{self.user.email} - {self.get_notification_type_display()}'