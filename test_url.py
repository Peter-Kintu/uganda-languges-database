#!/usr/bin/env python
"""Manual live-server smoke test. Run directly, never during test discovery."""
import requests


def main():
    response = requests.get(
        'http://127.0.0.1:8000/hotel/',
        allow_redirects=False,
        cookies={'sessionid': 'your_session'},
    )
    print(f'Status: {response.status_code}')
    print(f'Location: {response.headers.get("Location", "N/A")}')
    print(f'URL: {response.url}')


if __name__ == '__main__':
    main()
