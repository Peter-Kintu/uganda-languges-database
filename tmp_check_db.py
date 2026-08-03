import os
import sqlite3
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
import django
django.setup()
from django.conf import settings
print('BASE_DIR', settings.BASE_DIR)
print('DEBUG', settings.DEBUG)
print('DATABASES', settings.DATABASES['default'])
db = settings.DATABASES['default'].get('NAME')
print('DB name repr', repr(db))
print('DB exists', Path(db).exists() if db else 'no db name')
conn = sqlite3.connect(str(db))
cur = conn.cursor()
cur.execute('PRAGMA table_info(eshop_product)')
print('columns')
for col in cur.fetchall():
    print(col)
conn.close()
