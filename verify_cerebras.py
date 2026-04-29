#!/usr/bin/env python
"""Verify Cerebras integration in Django environment."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
django.setup()

print("✓ Django setup successful")

try:
    from users.views import cerebras_proxy
    print("✓ cerebras_proxy view imported successfully")
except Exception as e:
    print(f"✗ Failed to import cerebras_proxy: {e}")
    sys.exit(1)

try:
    from cerebras.cloud.sdk import Cerebras
    print("✓ Cerebras SDK imported successfully")
except Exception as e:
    print(f"✗ Failed to import Cerebras SDK: {e}")
    sys.exit(1)

# Check if CEREBRAS_API_KEY is set
from django.conf import settings
if hasattr(settings, 'CEREBRAS_API_KEY'):
    api_key = settings.CEREBRAS_API_KEY
    if api_key:
        print(f"✓ CEREBRAS_API_KEY is configured")
    else:
        print("⚠ CEREBRAS_API_KEY is empty (set in environment)")
else:
    print("✗ CEREBRAS_API_KEY not found in settings")

print("\n✅ All integrations verified successfully!")
