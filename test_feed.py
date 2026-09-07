#!/usr/bin/env python
import os
import sys


def main():
    import django

    sys.path.append('c:\\Users\\NIIH\\Desktop\\uganda-languges-database')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
    django.setup()

    from django.contrib.auth import get_user_model
    from django.test import Client

    user_model = get_user_model()
    client = Client()
    print('Testing social feed...')
    response = client.get('/hotels/')
    print(f'Status: {response.status_code}')
    print(f'Redirect: {response.get("Location", "None")}')

    user = user_model.objects.first()
    if not user:
        print('No users found')
        return
    client.force_login(user)
    response = client.get('/hotels/')
    print(f'Logged in status: {response.status_code}')
    print('SUCCESS: Social Feed page loaded' if 'Social Feed' in response.content.decode() else 'WARNING: Social Feed title not found')


if __name__ == '__main__':
    main()
