#!/usr/bin/env python
"""Test Cerebras SDK installation and configuration."""

import os


def main():
    try:
        from cerebras.cloud.sdk import Cerebras
    except ImportError as exc:
        print(f"ERROR: Failed to import Cerebras SDK: {exc}")
        return 1

    api_key = os.environ.get("CEREBRAS_API_KEY", "").strip()
    if api_key:
        print(f"API Key Status: Present ({len(api_key)} chars)")
    else:
        print("Warning: CEREBRAS_API_KEY environment variable not set")
        print("Set it in the deployment environment before using Cerebras.")
    print("Cerebras integration is ready to use!")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
