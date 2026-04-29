import os
import requests
import base64

CAREERJET_API_KEY = os.getenv('CAREERJET_PUBLISHER_ID', 'a9927b4ab404ffaff0e637290f35b7a8')
url = 'https://search.api.careerjet.net/v4/query'
params = {
    'locale_code': 'en_GB',
    'keywords': 'jobs',
    'location': 'Uganda',
    'page_size': 5,
    'user_ip': '154.72.205.234',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'sort': 'date',
}
credentials = base64.b64encode(f"{CAREERJET_API_KEY}:".encode()).decode()
headers = {
    'Authorization': f'Basic {credentials}',
    'User-Agent': params['user_agent'],
    'Accept': 'application/json',
    'Referer': 'https://www.careerjet.net/',
}
print('URL:', url)
print('Headers:', headers)
print('Params:', params)
resp = requests.get(url, headers=headers, params=params, timeout=20)
print('Status:', resp.status_code)
print('Headers:', resp.headers)
print('Body:', resp.text[:1000])
