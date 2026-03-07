import os
import requests
from movie.models import Movie


def fetch_and_store_movies():
    # Retrieve the token from environment variables
    token = os.environ.get('TMDB_TOKEN')

    url = "https://api.themoviedb.org/3/trending/movie/day?language=en-US"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    print("Fetching movies from TMDB...")
    response = requests.get(url, headers=headers)

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
            print(f"{'✅ Added' if created else '🔄 Updated'}: {item['title']}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")


if __name__ == "__main__":
    # Only set up Django if running standalone
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
    django.setup()
    fetch_and_store_movies()