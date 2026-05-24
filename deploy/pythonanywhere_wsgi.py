import os
import sys


USERNAME = "rmendoza"
PROJECT = "sistemaImport"
PROJECT_PATH = f"/home/{USERNAME}/{PROJECT}"


if PROJECT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_PATH)


os.environ["DJANGO_SETTINGS_MODULE"] = "import_manager.settings"
os.environ["DJANGO_ENV"] = "production"
os.environ["DEBUG"] = "false"
os.environ["SECRET_KEY"] = "cambia-esta-clave-por-una-secret-key-larga-generada-en-pythonanywhere"
os.environ["ALLOWED_HOSTS"] = f"{USERNAME}.pythonanywhere.com"
os.environ["CSRF_TRUSTED_ORIGINS"] = f"https://{USERNAME}.pythonanywhere.com"
os.environ["SECURE_SSL_REDIRECT"] = "true"
os.environ["SESSION_COOKIE_SECURE"] = "true"
os.environ["CSRF_COOKIE_SECURE"] = "true"
os.environ["SECURE_HSTS_PRELOAD"] = "false"


from django.core.wsgi import get_wsgi_application


application = get_wsgi_application()
