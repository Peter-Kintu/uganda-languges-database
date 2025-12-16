import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')

# This MUST be named 'application'
application = get_wsgi_application()