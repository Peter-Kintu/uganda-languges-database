#!/usr/bin/env python
import os
import django
import sys

# Setup Django
sys.path.append('c:\\Users\\NIIH\\Desktop\\uganda-languges-database')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
client = Client()

print("Testing social feed...")

# Try to access social feed without login
response = client.get('/hotels/')
print(f'Status: {response.status_code}')
print(f'Redirect: {response.get("Location", "None")}')

# Try with a logged in user
user = User.objects.first()
if user:
    print(f"Testing with user: {user.username}")
    client.force_login(user)
    response = client.get('/hotels/')
    print(f'Logged in status: {response.status_code}')
    content = response.content.decode()
    if 'Social Feed' in content:
        print('SUCCESS: Social Feed page loaded')
        if 'for feed_item in feed_items' in content:
            print('SUCCESS: Template loop found')
        else:
            print('INFO: Template loop not found')
        if 'feed_item' in content:
            print('SUCCESS: feed_item found in response')
            # Count how many feed items
            feed_count = content.count('feed_item')
            print(f'Found {feed_count} feed_item references')
        else:
            print('INFO: feed_item not found, but page loaded')
            # Check for post content
            if 'bg-white rounded-lg' in content:
                print('INFO: Post containers found')
            else:
                print('WARNING: No post containers found')
    else:
        print('WARNING: Social Feed title not found in response')
        # Show a snippet of the response
        print('Response snippet:', content[:500])
else:
    print("No users found")