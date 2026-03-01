"""
Django settings for Livestock Management System.

Sistema profissional de gestão de rebanhos com foco em:
- Alta performance e consistência de dados
- Arquitetura limpa (Clean Architecture + DDD leve)
- Preparado para evolução futura (possível SaaS)
- Segurança e auditoria completas
"""

import os
from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# CORE SETTINGS
# ==============================================================================

SECRET_KEY = config('SECRET_KEY', default='django-insecure-CHANGE-THIS-IN-PRODUCTION-abc123xyz789')

DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Configuração de site (usado em emails)
SITE_NAME = config('SITE_NAME', default='Gestão de Rebanhos')
SITE_DOMAIN = config('SITE_DOMAIN', default='localhost:8000')
SITE_PROTOCOL = 'https' if not DEBUG else 'http'


# ==============================================================================
# APPLICATION DEFINITION
# ==============================================================================

INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',  # Para formatação de números e datas

    # Third-party apps
    'django_extensions',
    'django_htmx',

    # Local apps
    'core.apps.CoreConfig',
    'farms.apps.FarmsConfig',
    'inventory.apps.InventoryConfig',
    'operations.apps.OperationsConfig',
    'reporting.apps.ReportingConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve arquivos estáticos em produção
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

# ==============================================================================
# TEMPLATES
# FIX: APP_DIRS=False + loaders explícitos permitem que o bloco de produção
# substitua os loaders pelo cached.Loader sem conflito.
# Com APP_DIRS=True não é possível definir 'loaders' em OPTIONS.
# ==============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',  # Templates globais
        ],
        'APP_DIRS': False,  # ← CORRIGIDO: False para permitir loaders customizados
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',  # Para MEDIA_URL
                'django.template.context_processors.static',  # Para STATIC_URL
            ],
            'loaders': [  # ← CORRIGIDO: loaders explícitos substituem APP_DIRS=True
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ==============================================================================
# DATABASE
# ==============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='livestock_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5433'),
        'ATOMIC_REQUESTS': True,  # Transações automáticas por request
        'CONN_MAX_AGE': 600,  # Conexões persistentes (10 min)
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Database optimization
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Connection pooling (opcional - requer django-db-geventpool ou pgbouncer)
# DATABASES['default']['CONN_MAX_AGE'] = None


# ==============================================================================
# PASSWORD VALIDATION
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ==============================================================================
# INTERNATIONALIZATION
# ==============================================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Formatos de data customizados
DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y H:i'
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'

# Formatos de número
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','
NUMBER_GROUPING = 3


# ==============================================================================
# STATIC FILES (CSS, JavaScript, Images)
# ==============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Compressão e cache de arquivos estáticos em produção
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ==============================================================================
# REDIS CACHE
# ==============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'livestock',
        'TIMEOUT': 300,
        'VERSION': 1,
    }
}

# Session engine (opcional - usar cache para sessions)
# SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
# SESSION_CACHE_ALIAS = 'default'
# SESSION_COOKIE_AGE = 1209600  # 2 semanas


# ==============================================================================
# CELERY CONFIGURATION
# ==============================================================================

CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/0')

CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery task settings
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutos
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutos
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Celery Beat (agendamento de tarefas)
CELERY_BEAT_SCHEDULE = {
    # Exemplo: reconciliação automática de estoque
    # 'reconcile-stock-daily': {
    #     'task': 'inventory.tasks.reconcile_all_stocks',
    #     'schedule': crontab(hour=2, minute=0),  # 02:00 AM
    # },
}


# ==============================================================================
# LOGGING
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'colored': {
            'format': '{levelname} {asctime} [{module}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'colored',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'livestock.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'file_errors': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'file_security': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file_errors', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file_security'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING' if DEBUG else 'ERROR',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'farms': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'inventory': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'operations': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'reporting': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Criar diretórios necessários
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


# ==============================================================================
# SECURITY SETTINGS
# ==============================================================================

if not DEBUG:
    # HTTPS
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
    SECURE_CROSS_ORIGIN_RESOURCE_POLICY = "same-origin"
    X_FRAME_OPTIONS = 'DENY'

    # Cookie security
    CSRF_COOKIE_HTTPONLY = False
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = "Lax"

    # Referrer policy
    SECURE_REFERRER_POLICY = 'same-origin'

else:
    # Development - configurações mais permissivas
    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]


# ==============================================================================
# BUSINESS RULES CONFIGURATION
# ==============================================================================

# Configurações específicas do domínio de negócio

# Controle de estoque
STOCK_BALANCE_RECONCILIATION_ENABLED = config(
    'STOCK_BALANCE_RECONCILIATION_ENABLED',
    default=True,
    cast=bool
)
STOCK_BALANCE_AUTO_RECONCILE_ON_INCONSISTENCY = config(
    'STOCK_BALANCE_AUTO_RECONCILE_ON_INCONSISTENCY',
    default=False,
    cast=bool
)

# Tolerância para diferenças de estoque (quantidade de animais)
STOCK_BALANCE_TOLERANCE = config('STOCK_BALANCE_TOLERANCE', default=0, cast=int)

# Relatórios
REPORT_CACHE_TIMEOUT = config('REPORT_CACHE_TIMEOUT', default=3600, cast=int)  # 1 hora
REPORT_MAX_MONTHS_RANGE = config('REPORT_MAX_MONTHS_RANGE', default=12, cast=int)
REPORT_PDF_GENERATION_TIMEOUT = config('REPORT_PDF_GENERATION_TIMEOUT', default=60, cast=int)

# Auditoria
TRACK_USER_IP = config('TRACK_USER_IP', default=True, cast=bool)
ENABLE_MOVEMENT_AUDIT_LOG = config('ENABLE_MOVEMENT_AUDIT_LOG', default=True, cast=bool)
AUDIT_LOG_RETENTION_DAYS = config('AUDIT_LOG_RETENTION_DAYS', default=365, cast=int)

# Limites e validações
MAX_QUANTITY_PER_MOVEMENT = config('MAX_QUANTITY_PER_MOVEMENT', default=10000, cast=int)
ALLOW_NEGATIVE_STOCK = config('ALLOW_NEGATIVE_STOCK', default=False, cast=bool)

# Features flags
ENABLE_NOTIFICATIONS = config('ENABLE_NOTIFICATIONS', default=True, cast=bool)
ENABLE_EXPORTS = config('ENABLE_EXPORTS', default=True, cast=bool)
ENABLE_BATCH_OPERATIONS = config('ENABLE_BATCH_OPERATIONS', default=True, cast=bool)


# ==============================================================================
# EMAIL CONFIGURATION
# ==============================================================================

if DEBUG:
    # Console backend para desenvolvimento
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    # SMTP backend para produção
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=30, cast=int)

    # Fallback para console se não configurado
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Configurações de email
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL',
    default=f'{SITE_NAME} <noreply@{SITE_DOMAIN.split(":")[0]}>'
)
SERVER_EMAIL = config('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)
ADMINS = [
    ('Admin', config('ADMIN_EMAIL', default='admin@localhost')),
]
MANAGERS = ADMINS

# Email de notificações
NOTIFICATION_EMAIL_ENABLED = config('NOTIFICATION_EMAIL_ENABLED', default=True, cast=bool)
NOTIFICATION_EMAIL_PREFIX = config('NOTIFICATION_EMAIL_PREFIX', default=f'[{SITE_NAME}]')


# ==============================================================================
# AUTHENTICATION & AUTHORIZATION
# ==============================================================================

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Session settings
SESSION_COOKIE_NAME = 'livestock_sessionid'
SESSION_COOKIE_AGE = 1209600  # 2 semanas
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# CSRF settings
CSRF_COOKIE_NAME = "livestock_csrftoken"
CSRF_COOKIE_AGE = 60 * 60 * 24 * 365  # 1 ano

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://rebanho.ferzion.com.br,https://www.rebanho.ferzion.com.br",
    cast=Csv(),
)

# Password reset
PASSWORD_RESET_TIMEOUT = 259200  # 3 dias (em segundos)


# ==============================================================================
# PERFORMANCE OPTIMIZATIONS
# ==============================================================================

# Template caching em produção
# FIX: Funciona corretamente pois APP_DIRS=False + loaders já estão definidos acima.
# O cached.Loader encapsula os loaders base para cache em memória em produção.
if not DEBUG:
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]

# Query optimization
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# File uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644


# ==============================================================================
# THIRD-PARTY APPS CONFIGURATION
# ==============================================================================

# Django Extensions
SHELL_PLUS = 'ipython'
SHELL_PLUS_PRINT_SQL = DEBUG

# Django HTMX
HTMX_BOOSTED = True  # Ativa HTMX boosting automaticamente


# ==============================================================================
# CUSTOM SETTINGS
# ==============================================================================

# Versionamento da API (futuro)
API_VERSION = 'v1'

# Modo de manutenção
MAINTENANCE_MODE = config('MAINTENANCE_MODE', default=False, cast=bool)

# Feature flags adicionais
FEATURES = {
    'reports': config('FEATURE_REPORTS', default=True, cast=bool),
    'exports': config('FEATURE_EXPORTS', default=True, cast=bool),
    'notifications': config('FEATURE_NOTIFICATIONS', default=True, cast=bool),
    'audit': config('FEATURE_AUDIT', default=True, cast=bool),
}


# ==============================================================================
# DEVELOPMENT TOOLS
# ==============================================================================

if DEBUG:
    # Debug toolbar (se instalado)
    try:
        import debug_toolbar
        INSTALLED_APPS += ['debug_toolbar']
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        DEBUG_TOOLBAR_CONFIG = {
            'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
        }
    except ImportError:
        pass

    # Django extensions shell plus
    SHELL_PLUS_IMPORTS = [
        'from django.db.models import Q, F, Count, Sum, Avg',
        'from datetime import datetime, timedelta, date',
        'from django.utils import timezone',
    ]


# ==============================================================================
# ENVIRONMENT VALIDATION
# ==============================================================================

# Validar configurações críticas em produção
if not DEBUG:
    critical_configs = [
        'SECRET_KEY',
        'DB_PASSWORD',
    ]

    for cfg in critical_configs:
        if cfg == 'SECRET_KEY' and SECRET_KEY == 'django-insecure-CHANGE-THIS-IN-PRODUCTION-abc123xyz789':
            raise ValueError(f"Configure {cfg} em produção!")
        elif cfg == 'DB_PASSWORD' and config(cfg, default='postgres') == 'postgres':
            raise ValueError(f"Configure {cfg} com valor seguro em produção!")