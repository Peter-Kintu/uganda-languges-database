#!/usr/bin/env python
"""Test Cerebras API connection."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
django.setup()

from cerebras.cloud.sdk import Cerebras

def test_cerebras_api():
    api_key = os.environ.get("CEREBRAS_API_KEY", "").strip()
    if not api_key:
        print("❌ CEREBRAS_API_KEY not set")
        return False

    print(f"✓ API Key found: {api_key[:10]}...{api_key[-5:]}")

    try:
        client = Cerebras(api_key=api_key)
        print("✓ Cerebras client initialized")

        # Test simple completion
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ]

        completion = client.chat.completions.create(
            messages=messages,
            model="llama3.1-8b",
            max_completion_tokens=100,
            temperature=0.7,
            top_p=1,
            stream=False,
        )

        response_text = completion.choices[0].message.content if completion.choices else ""
        if response_text:
            print("✓ API call successful!")
            print(f"Response: {response_text[:100]}...")
            return True
        else:
            print("❌ Empty response from API")
            return False

    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_cerebras_api()
    sys.exit(0 if success else 1)