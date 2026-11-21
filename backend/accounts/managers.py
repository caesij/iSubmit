from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    def _create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')

        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, email, password=None, **extra_fields):
        if 'role' not in extra_fields:
            raise ValueError('A permission role must be assigned.')

        return self._create_user(email, password, **extra_fields)

    def create_faculty_user(self, email, password=None, **extra_fields):
        from role_management.models import Role

        extra_fields.setdefault(
            'role',
            Role.objects.get(code=Role.Code.FACULTY, is_default=True),
        )

        return self._create_user(email, password, **extra_fields)

    def create_staff_user(self, email, password=None, **extra_fields):
        from role_management.models import Role

        extra_fields.setdefault(
            'role',
            Role.objects.get(code=Role.Code.STAFF, is_default=True),
        )

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        from role_management.models import Role

        extra_fields['role'] = Role.objects.get(
            code=Role.Code.ADMIN,
            is_default=True,
        )

        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields['is_superuser'] is not True:
            raise ValueError('A superuser must have is_superuser=True.')

        if extra_fields['is_staff'] is not True:
            raise ValueError('A superuser must have is_staff=True.')

        if extra_fields['is_active'] is not True:
            raise ValueError('A superuser must have is_active=True.')

        return self._create_user(email, password, **extra_fields)


class FacultyManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(
            role__code='FACULTY',
            role__is_default=True,
        )


class StaffManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(
            role__code='STAFF',
            role__is_default=True,
        )
