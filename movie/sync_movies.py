import os
import requests
from movie.models import Movie


def fetch_and_store_movies():
    # Retrieve the v3 API key from environment variables
    token = os.environ.get('TMDB_TOKEN')

    url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={token}&language=en-US"
    headers = {"accept": "application/json"}

    print("Fetching movies from TMDB...")
    response = requests.get(url, headers=headers)

    added_count = 0
    updated_count = 0

    if response.status_code == 200:
        data = response.json().get('results', [])
        for item in data:
            # Create a basic Amazon affiliate link using the movie title
            search_query = item['title'].replace(" ", "+")
            amazon_affiliate = f"https://www.amazon.com/s?k={search_query}+movie"

            movie, created = Movie.objects.update_or_create(
                name=item['title'],
                defaults={
                    'description': item['overview'],
                    'genre': 'Trending',
                    'rating': item['vote_average'],
                    'image_url': f"https://image.tmdb.org/t/p/w500{item['poster_path']}",
                    'affiliate_url': amazon_affiliate,
                    'ai_summary': f"AI Pick: {item['title']} is currently trending!",
                }
            )
            if created:
                added_count += 1
                print(f"✅ Added: {item['title']}")
            else:
                updated_count += 1
                print(f"🔄 Updated: {item['title']}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")

    return added_count, updated_count


if __name__ == "__main__":
    # Only set up Django if running standalone
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
    django.setup()
    added, updated = fetch_and_store_movies()
    print(f"Finished syncing. Added: {added}, Updated: {updated}")