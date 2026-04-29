#!/usr/bin/env python
"""Test Cerebras SDK installation and configuration."""

import os
import sys

try:
    from cerebras.cloud.sdk import Cerebras
    print("SUCCESS: Cerebras SDK imported successfully")
except ImportError as e:
    print(f"ERROR: Failed to import Cerebras SDK: {e}")
    sys.exit(1)

# Check API key
api_key = os.environ.get("CEREBRAS_API_KEY", "").strip()
if api_key:
    print(f"API Key Status: Present ({len(api_key)} chars)")
else:
    print("Warning: CEREBRAS_API_KEY environment variable not set")
    print("Set it with: export CEREBRAS_API_KEY=your_key_here")

print("\nCerebras integration is ready to use!")
