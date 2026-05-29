import os
import requests
from movie.models import Movie


def fetch_and_store_movies():
    # Retrieve the v3 API token from environment variables
    token = os.environ.get('TMDB_TOKEN')
    headers = {"accept": "application/json"}

    added_count = 0
    updated_count = 0

    # 1. DEFINE AFRICAN COUNTRIES TO SOURCE FROM (ISO 3166-1 codes)
    african_countries = ['NG', 'ZA', 'KE', 'GH', 'UG']

    print("Sourcing African Cinema from TMDB...")
    for country in african_countries:
        discover_url = (
            f"https://api.themoviedb.org/3/discover/movie?api_key={token}"
            f"&language=en-US&sort_by=popularity.desc&with_origin_country={country}&page=1"
        )
        try:
            response = requests.get(discover_url, headers=headers, timeout=15)
            if response.status_code == 200:
                results = response.json().get('results', [])
                for item in results:
                    if not item.get('title'):
                        continue

                    search_query = item['title'].replace(" ", "+")
                    amazon_affiliate = f"https://www.amazon.com/s?k={search_query}+movie"

                    movie, created = Movie.objects.update_or_create(
                        name=item['title'],
                        defaults={
                            'description': item.get('overview', ''),
                            'genre': 'African Cinema',
                            'rating': item.get('vote_average', 0),
                            'image_url': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else "",
                            'affiliate_url': amazon_affiliate,
                            'ai_summary': f"Africana Spotlight: Explore authentic storytelling in {item['title']}!",
                        }
                    )
                    if created:
                        added_count += 1
                    else:
                        updated_count += 1
        except Exception as e:
            print(f"Skipping country {country} due to an error: {e}")

    # 2. SOURCE GLOBAL TRENDING MOVIES AS A MINORITY FILLER
    print("Sourcing global trending filler movies...")
    trending_url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={token}&language=en-US"
    try:
        trending_resp = requests.get(trending_url, headers=headers, timeout=15)
        if trending_resp.status_code == 200:
            trending_results = trending_resp.json().get('results', [])[:8]
            for item in trending_results:
                if not item.get('title'):
                    continue

                # Prevent overwriting an African movie's custom metadata
                if Movie.objects.filter(name=item['title'], genre='African Cinema').exists():
                    continue

                search_query = item['title'].replace(" ", "+")
                amazon_affiliate = f"https://www.amazon.com/s?k={search_query}+movie"

                movie, created = Movie.objects.update_or_create(
                    name=item['title'],
                    defaults={
                        'description': item.get('overview', ''),
                        'genre': 'Trending Global',
                        'rating': item.get('vote_average', 0),
                        'image_url': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else "",
                        'affiliate_url': amazon_affiliate,
                        'ai_summary': f"AI Pick: {item['title']} is currently trending globally!",
                    }
                )
                if created:
                    added_count += 1
                else:
                    updated_count += 1
    except Exception as e:
        print(f"Trending fetch failed: {e}")

    return added_count, updated_count


if __name__ == "__main__":
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myuganda.settings')
    django.setup()
    added, updated = fetch_and_store_movies()
    print(f"Finished syncing. Added: {added}, Updated: {updated}")