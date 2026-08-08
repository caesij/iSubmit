from django.contrib.auth.base_user import BaseUserManager

class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email is required.')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_faculty_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', self.model.Role.FACULTY)
        return self._create_user(email, password, **extra_fields)

    def create_staff_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', self.model.Role.STAFF)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["role"] = self.model.Role.ADMIN
        extra_fields.setdefault("is_active", True)
        return self._create_user(email, password, **extra_fields)

class FacultyManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(role=self.model.Role.FACULTY)

class StaffManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(role=self.model.Role.STAFF)