"""
Configuración de Django para FíaFácil.

Los valores sensibles (clave secreta, contraseña de la base de datos, canales
de soporte) se leen del archivo .env con python-dotenv. Ver .env.example.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga las variables de .env (si existe) sin pisar las que ya estén definidas
# en el sistema operativo; así un despliegue puede usar variables reales.
load_dotenv(BASE_DIR / ".env")


def _env_bool(nombre, por_defecto=False):
    """Interpreta 'True', '1', 'si' o 'yes' (sin importar mayúsculas) como verdadero."""
    valor = os.getenv(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes"}


def _env_lista(nombre, por_defecto=""):
    """Convierte 'a,b,c' en ['a', 'b', 'c'] ignorando espacios y vacíos."""
    return [x.strip() for x in os.getenv(nombre, por_defecto).split(",") if x.strip()]


# --- Seguridad --------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "")
DEBUG = _env_bool("DEBUG", False)
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "solo-para-desarrollo-no-usar-en-produccion"
    else:
        raise RuntimeError("Falta SECRET_KEY en el archivo .env (obligatoria con DEBUG=False).")

ALLOWED_HOSTS = _env_lista("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _env_lista("CSRF_TRUSTED_ORIGINS")

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 8  # la sesión dura una jornada (8 horas)
X_FRAME_OPTIONS = "DENY"


# --- Aplicaciones -----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Apps propias de FíaFácil
    "cuentas.apps.CuentasConfig",
    "tiendas.apps.TiendasConfig",
    "clientes.apps.ClientesConfig",
    "creditos.apps.CreditosConfig",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "cuentas.middleware.TiendaActivaMiddleware",  # request.tienda según la membresía (RN01)
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.contexto.fiafacil",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Base de datos: PostgreSQL vía psycopg 3 --------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "fiafacil"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        # Con USE_TZ=True, Django guarda fecha y hora como "timestamptz" (instante
        # absoluto) y trabaja la sesión de la base en UTC; la conversión a hora de
        # Lima se hace en Python con TIME_ZONE. Así no hay ambigüedad en el corte.
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Usuarios y autenticación -----------------------------------------------

# Usuario propio: inicia sesión con su correo y su id es un UUID.
AUTH_USER_MODEL = "cuentas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

import sys  # noqa: E402

# Solo al ejecutar "manage.py test": un hash de contraseñas rápido para que la
# suite no tarde minutos. En uso normal se mantiene PBKDF2 (el seguro de Django).
if len(sys.argv) > 1 and sys.argv[1] == "test":
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LOGIN_URL = "cuentas:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "cuentas:login"


# --- Idioma, zona horaria y formatos peruanos -------------------------------

LANGUAGE_CODE = "es-pe"
LANGUAGES = [("es-pe", "Español (Perú)")]
TIME_ZONE = "America/Lima"  # RN03: el corte se evalúa en hora de Lima
USE_I18N = True
USE_TZ = True  # en la base se guarda en UTC; se muestra y calcula en hora de Lima

# Formatos propios (config/formatos/es_PE/formats.py): punto decimal y fechas
# dd/mm/aaaa. Prevalecen sobre los formatos del español genérico de Django,
# que usan coma decimal.
FORMAT_MODULE_PATH = ["config.formatos"]
USE_THOUSAND_SEPARATOR = False  # los importes se formatean con el filtro propio "dinero"


# --- Archivos estáticos e imágenes ------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# RN11: la imagen del artículo es obligatoria y pesa como máximo 2 MB.
IMAGEN_MAX_BYTES = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024


# --- Mensajes con clases de Bootstrap ---------------------------------------

from django.contrib.messages import constants as mensajes  # noqa: E402

MESSAGE_TAGS = {
    mensajes.DEBUG: "secondary",
    mensajes.INFO: "info",
    mensajes.SUCCESS: "success",
    mensajes.WARNING: "warning",
    mensajes.ERROR: "danger",
}


# --- Soporte (botón flotante de WhatsApp y correo en la ayuda) --------------

SOPORTE_WHATSAPP = os.getenv("SOPORTE_WHATSAPP", "")
SOPORTE_CORREO = os.getenv("SOPORTE_CORREO", "")
