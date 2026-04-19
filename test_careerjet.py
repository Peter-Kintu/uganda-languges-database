import os
import requests
import base64
import json

# Copy the necessary parts from views.py
CAREERJET_API_KEY = os.getenv("CAREERJET_PUBLISHER_ID", "a9927b4ab404ffaff0e637290f35b7a8")

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class MockRequest:
    def __init__(self):
        self.META = {
            'HTTP_USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'REMOTE_ADDR': '127.0.0.1'
        }

    def build_absolute_uri(self):
        return 'http://test.com/'

def fetch_careerjet_data(request, keywords, location="Uganda"):
    """
    CareerJet v4 API - PAID VERSION
    Must pass user_ip + user_agent + Referer or clicks won't count
    """
    if not keywords:
        keywords = "jobs"

    url = "https://search.api.careerjet.net/v4/query"

    # Required for tracking: real user data
    user_ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    referer = request.build_absolute_uri()

    params = {
        'locale_code': 'en_UG',  # Use en_UG for Uganda, not en_US
        'keywords': keywords,
        'location': location or "Uganda",
        'page_size': 20,
    }

    # Basic auth: API key + empty password
    credentials = base64.b64encode(f"{CAREERJET_API_KEY}:".encode()).decode()
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/json',
        'Referer': referer,  # MANDATORY or $0
        'user_ip': user_ip,        # MANDATORY or $0
        'user_agent': user_agent,  # MANDATORY or $0
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"API Response Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", [])
            normalized = []
            for job in jobs:
                normalized.append({
                    "source": "CareerJet",
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "location": job.get("locations"),
                    "salary": job.get("salary"),
                    "link": job.get("url"),  # This URL has tracking built-in
                })
            return normalized
        elif r.status_code == 403:
            print("CareerJet Error 403: Missing user_ip or user_agent")
        else:
            print(f"CareerJet Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"CareerJet API Error: {e}")
    return []

# Test the function
print("Testing CareerJet API fetch...")
request = MockRequest()
jobs = fetch_careerjet_data(request, 'developer', 'Uganda')
print(f"Found {len(jobs)} jobs from CareerJet")
for job in jobs[:3]:  # Show first 3 jobs
    print(f"- {job['title']} at {job['company']} in {job['location']}")
if jobs:
    print("✓ Jobs are being fetched successfully!")
    print("✓ Clicks should now be tracked with the new API.")
else:
    print("✗ No jobs returned - check API key or network.")