import os
from datetime import timedelta
from pathlib import Path  # Ensure this import exists

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG") != "False"

ROOT_URLCONF = "InsaBackednLatest.urls"
# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
ALLOWED_HOSTS.append("localhost")
ALLOWED_HOSTS.append("127.0.0.1")
ALLOWED_HOSTS.append("0.0.0.0")
ALLOWED_HOSTS.append("localhost:8010")
ALLOWED_HOSTS.append("192.168.10.42")
ALLOWED_HOSTS.append("host.docker.internal")
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# Custom user model
AUTH_USER_MODEL = "users.CustomUser"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT"),
        "CONN_MAX_AGE": 60, 
        "CONN_HEALTH_CHECKS": True, 
        "OPTIONS": {
            "connect_timeout": 10,  
            "options": "-c statement_timeout=30000"  
        },
    },
    "central": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": "local_postgres",
        "PORT": 5432,        
        "CONN_MAX_AGE": 60, 
        "CONN_HEALTH_CHECKS": True, 
        "OPTIONS": {
            "connect_timeout": 10,  
            "options": "-c statement_timeout=30000"  
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Task acknowledgment and reliability
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50

# Task time limits
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes soft limit
CELERY_TASK_TIME_LIMIT = 360  # 6 minutes hard limit

# Task retry policy
CELERY_TASK_RETRY_POLICY = {
    "max_retries": 3,
    "interval_start": 5,
    "interval_step": 10,
    "interval_max": 60,
}

# Default auto field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"



# Email settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = os.environ.get("EMAIL_PORT")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
WSGI_APPLICATION = "InsaBackednLatest.wsgi.application"
CORS_ALLOW_CREDENTIALS = os.environ.get("CORS_ALLOW_CREDENTIALS") == "True"
CORS_ALLOW_HEADERS = os.environ.get("CORS_ALLOW_HEADERS", "").split(",")

CORS_ALLOW_METHODS = os.environ.get("CORS_ALLOW_METHODS", "").split(",")


# JWT settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_LIFETIME", "15"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_LIFETIME", "1"))
    ),
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": os.environ.get("JWT_VERIFYING_KEY", SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_api_key",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    "auditlog",
    "drf_spectacular",
    "django_pandas",
    # Moved to correct position
    "drivers",
    "address",
    "tax",
    "exporters",
    "workstations",
    "trucks",
    "path",
    "news",
    "audit",
    "api",
    "users",
    "orcSync",
    "localcheckings",
    "declaracions",
    "analysis",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.AttachJWTTokenMiddleware",
    "common.middleware.RefreshTokenMiddleware",
    "common.middleware.DisplayCurrentUserMiddleware",
]
# External APIs and Tokens
DERASH_API_KEY = os.environ.get("DERASH_API_KEY")
DERASH_SECRET_KEY = os.environ.get("DERASH_SECRET_KEY")
DERASH_END_POINT = os.environ.get("DERASH_END_POINT")
WEIGHTBRIDGE_TOKEN = os.environ.get("WEIGHTBRIDGE_TOKEN")
EXTERNAL_URI_WEIGHT_BRIDGE = os.environ.get("EXTERNAL_URI_WEIGHT_BRIDGE")
STATIC_URL = "/static/"
# CORS and CSRF settings
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")

# Media settings
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/app/media")
MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

SYNCHRONIZABLE_MODELS = [
    "drivers.Driver",
    "workstations.WorkStation",
    "workstations.WorkedAt",
    "trucks.TruckOwner",
    "trucks.Truck",
    "exporters.TaxPayerType",
    "exporters.Exporter",
    "tax.Tax",
    "users.Report",
    "users.UserStatus",
    "users.CustomUser",
    "users.Department",
    "address.RegionOrCity",
    "address.ZoneOrSubcity",
    "address.Woreda",
    "declaracions.Commodity",
    "declaracions.PaymentMethod",
    "declaracions.Declaracion",
    "declaracions.Checkin",
    "declaracions.ChangeTruck",
    "declaracions.ManualPayment",
    "auth.Group",
    "path.Path",
    "path.PathStation",
]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ORC API Documentation",
    "DESCRIPTION": "Complete API documentation for the ORC (Oromia Revenue Commission) system. This API provides endpoints for managing addresses, users, trucks, workstations, drivers, declarations, exporters, tax, and more.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CONTACT": {
        "name": "ORC Development Team",
        "email": "contact@example.com",
    },
    "LICENSE": {
        "name": "BSD License",
    },
    "SERVERS": [
        {"url": "http://127.0.0.1:8000", "description": "Local Development Server"},
        {"url": "http://127.0.0.1:5002", "description": "Alternative Local Server"},
    ],
    # Schema generation settings
    "SCHEMA_PATH_PREFIX": r"/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    # Swagger UI settings
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
        "filter": True,
        "tryItOutEnabled": True,
    },
    # Security schemes
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
    "SECURITY": [{"bearerAuth": []}],
    # Preprocessing
    "PREPROCESSING_HOOKS": [],
    "POSTPROCESSING_HOOKS": [],
    # Enum settings
    "ENUM_NAME_OVERRIDES": {},
    # Component naming
    "COMPONENT_NO_READ_ONLY_REQUIRED": False,
}





