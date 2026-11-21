import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.conf import settings

from accounts.managers import UserManager, FacultyManager, StaffManager

def profile_picture_path(instance, filename):
    return f'profile_pictures/user_{instance.id}/{filename}'


class User(AbstractBaseUser, PermissionsMixin):
    # User Preferences
    class DateFormatChoice(models.TextChoices):
        LONG = 'F j, Y', 'MMMM DD, YYYY (June 1, 2026)'
        SHORT = 'm/d/Y', 'MM/DD/YYYY'
        ISO = 'Y-m-d', 'YYYY-MM-DD'

    class TimeFormatChoice(models.TextChoices):
        TWELVE = '12', '12-hour (AM/PM)'
        TWENTY_FOUR = '24', '24-hour'
    
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

    profile_picture = models.ImageField(
        upload_to=profile_picture_path,
        blank=True,
        null=True
    )

    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255)

    employee_ID = models.CharField(
        max_length=50,
        unique=True,
        error_messages={'unique': 'This employee ID is already in use.'}
    )

    email = models.EmailField(
        unique=True,
        error_messages={'unique': 'This email address is already in use.'}
    )

    role = models.ForeignKey(
        'role_management.Role',
        on_delete=models.PROTECT,
        related_name='users'
    )

    is_active = models.BooleanField(default=True)
    is_locked_out = models.BooleanField(default=False)

    locked_out_until = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [
        'first_name',
        'middle_name',
        'last_name',
        'employee_ID',
    ]

    def save(self, *args, **kwargs):
        if self.is_superuser:
            from role_management.models import Role

            self.role = Role.objects.get(
                code=Role.Code.ADMIN,
                is_default=True,
            )

        self.is_staff = self.is_superuser or self.role.is_admin_role

        update_fields = kwargs.get('update_fields')

        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add('is_staff')

            if self.is_superuser:
                update_fields.add('role')

            kwargs['update_fields'] = update_fields

        super().save(*args, **kwargs)

    def get_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(part for part in parts if part)

    def get_short_name(self):
        return self.email.split('@')[0]

    def __str__(self):
        return self.get_short_name()

    @property
    def role_key(self):
        return self.role.code

    @property
    def is_admin(self):
        return self.is_superuser or self.role.is_admin_role

    @property
    def is_faculty(self):
        return self.role.is_faculty_role

    @property
    def is_regular_staff(self):
        return self.role.is_staff_role


class FacultyProfile(models.Model):
    class FacultyType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full-Time Faculty'
        PART_TIME = 'PART_TIME', 'Part-Time Faculty'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='faculty_profile'
    )

    faculty_type = models.CharField(max_length=20, choices=FacultyType.choices)

    assigned_programs = models.ManyToManyField(
        'programs.Program',
        blank=True,
        related_name='faculty_members'
    )

    def __str__(self):
        return f'{self.user.get_full_name()} - Faculty Profile'


class FacultyAccount(User):
    objects = FacultyManager()
    class Meta:
        proxy = True
        verbose_name = 'Faculty Account'
        verbose_name_plural = 'Faculty Accounts'


class StaffAccount(User):
    objects = StaffManager()
    class Meta:
        proxy = True
        verbose_name = 'Staff Account'
        verbose_name_plural = 'Staff Accounts'


class SecurityLoginRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='security_login_records'
    )

    device_token_hash = models.CharField(max_length=64)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device_token_hash', 'session_key'],
                name='uniq_user_device_session'
            )
        ]

        indexes = [models.Index(fields=['user', 'expires_at'], name='acct_sec_login_exp_idx')]

    def __str__(self):
        return f'{self.user} - {self.user_agent}'
