import requests

r = requests.get('http://127.0.0.1:8000/hotel/', allow_redirects=False, cookies={'sessionid': 'your_session'})
print(f'Status: {r.status_code}')
print(f'Location: {r.headers.get("Location", "N/A")}')
print(f'URL: {r.url}')
