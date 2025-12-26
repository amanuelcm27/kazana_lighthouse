

from celery.schedules import crontab
from datetime import timedelta
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-zt0u6w0r$&ks*hprpmxzd==q6_*r94-p!t3sciptkr8w_wu=0='

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'sources',
    'processing',
    'matching',
    'notifications',
    "django_celery_beat",
    "django_celery_results",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lighthouse.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lighthouse.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME"),
        'USER': os.getenv("DB_USER"),
        'PASSWORD': os.getenv("DB_PASSWORD"),
        'HOST': os.getenv("DB_HOST"),
        'PORT': os.getenv("DB_PORT"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'

# EMAIL SETTINGS
CENTRAL_NOTIFICATION_EMAIL = os.getenv("CENTRAL_NOTIFICATION_EMAIL")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_PASS")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---- Celery Configuration ----
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Addis_Ababa"
CELERY_ENABLE_UTC = False

# Optional rate limiting + task control
CELERY_TASK_ACKS_LATE = True
# CELERY_TASK_TIME_LIMIT = 600  # 10 minutes per task
# CELERY_TASK_SOFT_TIME_LIMIT = 540

CELERY_BEAT_SCHEDULE = {
    "collect_google_links": {
        "task": "sources.tasks.collect_links_via_google_api_task",
        "schedule": timedelta(hours=1),
    },
    "refresh_google_queries": {
        "task": "sources.tasks.refresh_google_queries_task",
        "schedule": timedelta(hours=8, minutes=1),  
    },
    "run_scraper": {
        "task": "sources.tasks.run_scraper_task",
        "schedule": timedelta(hours=8),
    },
    "run_cleaners" : {
        "task" : "processing.tasks.run_cleaning_task",
        "schedule" : timedelta(hours=8, minutes=5)
    },
    "run_llm_extraction": {
        "task": "processing.tasks.run_llm_extraction_task",
        "schedule": timedelta(hours=8, minutes=10)
    },
    "run_matching": {
        "task" : "matching.tasks.run_matching_task",
        "schedule": timedelta(hours=8, minutes=15)
    },
    "run_email_digest": {
        "task" : "notifications.tasks.run_email_digest_task",
        "schedule": crontab(hour=0,minute=10, day_of_week='5')
    }

}

