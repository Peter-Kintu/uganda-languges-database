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

# Create a long post (more than 5 lines)
long_content = """This is a test post with multiple lines to test the Show More functionality.
Line 2: Testing if the content gets truncated properly when it exceeds 5 lines.
Line 3: This should trigger the Show More button to appear.
Line 4: The button should only show when the content is longer than 5 lines.
Line 5: This is getting close to the limit.
Line 6: This line should trigger the Show More button to appear since we now have more than 5 lines of content."""

post = Post.objects.create(
    author=user,
    content=long_content
)
print(f"Created long post with ID: {post.id}")

# Create another long post
long_content2 = """First line
Second line 
Third line
Fourth line
Fifth line
Sixth line - this triggers Show More
Seventh line to make it even longer
Eighth line
Ninth line
Tenth line - definitely needs Show More now"""

post2 = Post.objects.create(
    author=user,
    content=long_content2
)
print(f"Created another long post with ID: {post2.id}")

# Create a short post
short_post = Post.objects.create(
    author=user,
    content="This is a short post that should NOT have a Show More button."
)
print(f"Created short post with ID: {short_post.id}")

print("Posts created successfully!")
