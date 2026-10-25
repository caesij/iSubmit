from pathlib import Path
import os
from celery.schedules import crontab
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

# Core Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',') if os.environ.get('ALLOWED_HOSTS') else []


# Applications
INSTALLED_APPS = [
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'storages',
    'axes',
    'accounts',
    'submissions',
    'notifications.apps.NotificationsConfig',
    'admin_staff_portal',
    'faculty_portal',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.UserPreferencesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR.parent / 'frontend' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'libraries': {
                'core_extras': 'core.templatetags.core_extras',
            },
        },
    },
]


# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DB_URL'),
        conn_max_age=0,
        ssl_require=True,
    )
}


# File storage (Supabase S3-compatible)
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

AWS_ACCESS_KEY_ID = os.getenv('SUPABASE_S3_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('SUPABASE_S3_SECRET_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('BUCKET_NAME')
AWS_S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')
AWS_S3_REGION_NAME = os.getenv('S3_REGION_NAME')

# Supabase-Specific S3 Compatibility
AWS_S3_ADDRESSING_STYLE = 'path'
AWS_DEFAULT_ACL = None
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_QUERYSTRING_AUTH = True
AWS_S3_FILE_OVERWRITE = False


# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR.parent / 'frontend' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Auth
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'accounts:login'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]


# Django Axes
AXES_FAILURE_LIMIT = 5
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_USERNAME_FORM_FIELD = 'username'
AXES_LOCKOUT_CALLABLE = 'accounts.axes_handlers.lockout_response'
AXES_RESET_ON_SUCCESS = True
AXES_DISABLE_ACCESS_LOG = False
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False


# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASS')
DEFAULT_FROM_EMAIL = os.environ.get('EMAIL_USER')


# Security
X_FRAME_OPTIONS = 'SAMEORIGIN'
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

# Celery Settings
CELERY_BROKER_URL = os.getenv(
    'CELERY_BROKER_URL',
    f'redis://{REDIS_HOST}:{REDIS_PORT}/1',
)

CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CELERY_BEAT_SCHEDULE = {
    'delete-expired-archived-documents-daily': {
        'task': 'submissions.delete_expired_archived_documents',
        'schedule': crontab(hour=3, minute=0),
    },
    
    'release-expired-account-lockouts': {
        'task': 'accounts.tasks.release_expired_account_lockouts',
        'schedule': 60.0,
    }
}