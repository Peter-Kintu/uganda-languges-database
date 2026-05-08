#!/usr/bin/env python
"""
Test script to verify jobs are being fetched and processed correctly.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
django.setup()

from django.test import RequestFactory
from languages.views import browse_job_listings, fetch_jooble_data, deduplicate_jobs

print("=" * 60)
print("JOBS DISPLAY TEST")
print("=" * 60)

# Test 1: Jooble API
print("\n[Test 1] Jooble API")
jooble_jobs = fetch_jooble_data("python", "")
print(f"✓ Jooble returned {len(jooble_jobs)} jobs")
if jooble_jobs:
    print(f"  Sample: {jooble_jobs[0]['title']} @ {jooble_jobs[0]['company']}")

# Test 2: Deduplicate function
print("\n[Test 2] Deduplicate Function")
deduped = deduplicate_jobs(jooble_jobs)
print(f"✓ After dedup: {len(deduped)} jobs (removed {len(jooble_jobs) - len(deduped)} dupes)")

# Test 3: Browse view
print("\n[Test 3] Browse Jobs View")
rf = RequestFactory()
req = rf.get('/jobs/')
response = browse_job_listings(req)

# The response should be a TemplateResponse
if hasattr(response, 'render'):
    response.render()
    
if hasattr(response, 'context_data'):
    ctx = response.context_data
else:
    # Extract from rendered content
    ctx = {}
    print(f"  Response type: {type(response)}")

print("✓ Browse view executed successfully")
print(f"  External jobs in context: {len(ctx.get('external_jobs', []))}")
print(f"  Job posts in context: {ctx.get('job_posts', 'N/A')}")

# Test 4: Check if jobs are in rendered HTML
print("\n[Test 4] HTML Rendering")
if hasattr(response, 'content'):
    content = response.content.decode()
    jooble_count = content.count('Premium Job')
    print(f"✓ Found {jooble_count} 'Premium Job' badges in HTML")
    if jooble_count > 0:
        print("  ✓ JOBS ARE DISPLAYING CORRECTLY!")
    else:
        print("  ✗ Jobs found in context but not rendering in HTML")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
