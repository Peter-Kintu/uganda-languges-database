import os
print('CEREBRAS_API_KEY:', os.environ.get('CEREBRAS_API_KEY', 'NOT SET'))

# Test basic import
try:
    from cerebras.cloud.sdk import Cerebras
    print('✓ Cerebras SDK imported successfully')
except ImportError as e:
    print('✗ Cerebras SDK import failed:', e)

# Test API call if key is available
api_key = os.environ.get('CEREBRAS_API_KEY', '').strip()
if api_key:
    try:
        client = Cerebras(api_key=api_key)
        print('✓ Cerebras client initialized')

        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello"}],
            model="llama3.1-8b",
            max_completion_tokens=50,
        )

        response = completion.choices[0].message.content if completion.choices else ""
        print('✓ API call successful:', response[:50] + '...' if response else 'Empty response')
    except Exception as e:
        print('✗ API call failed:', str(e))
else:
    print('✗ No API key found')