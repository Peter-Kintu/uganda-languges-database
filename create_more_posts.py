#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
django.setup()

from django.contrib.auth import get_user_model
from hotel.models import Post

User = get_user_model()
user = User.objects.first()

if not user:
    print("No user found!")
    exit(1)

# Create many more posts to test Load More
for i in range(25, 35):
    content = f"""This is test post number {i}.
This post has multiple lines to test the Show More functionality.
Line 2: Testing if the content gets truncated properly.
Line 3: This should trigger the Show More button to appear for initial posts.
Line 4: But loaded posts should show full content without Show More.
Line 5: This is getting close to the limit.
Line 6: This line should trigger the Show More button for initial posts only."""

    post = Post.objects.create(author=user, content=content)
    print(f"Created post {i} with ID: {post.id}")

print("All test posts created!")