from html import escape

from django.test import TestCase
from django.urls import reverse

from .content import ARTICLES


class EditorialPageTests(TestCase):
    def test_article_index_lists_all_original_articles(self):
        response = self.client.get(reverse("editorial:article_index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(ARTICLES), 18)
        for article in ARTICLES:
            self.assertContains(response, escape(article["title"]))
            self.assertContains(
                response,
                reverse("editorial:article_detail", kwargs={"slug": article["slug"]}),
            )

    def test_article_full_text_is_in_server_response(self):
        article = ARTICLES[0]
        response = self.client.get(
            reverse("editorial:article_detail", kwargs={"slug": article["slug"]})
        )

        self.assertEqual(response.status_code, 200)
        for paragraph in article["paragraphs"]:
            self.assertContains(response, paragraph)
        self.assertContains(
            response,
            f'<link rel="canonical" href="https://www.africanaai.info/articles/{article["slug"]}/">',
            html=True,
        )

    def test_unknown_article_returns_not_found(self):
        response = self.client.get(
            reverse("editorial:article_detail", kwargs={"slug": "not-an-article"})
        )

        self.assertEqual(response.status_code, 404)

    def test_legal_pages_are_public_and_linked_in_global_footer(self):
        for route_name, heading in (
            ("privacy_policy", "Privacy Policy"),
            ("terms_of_use", "Terms of Use"),
        ):
            response = self.client.get(reverse(route_name))

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, heading)
            self.assertContains(response, reverse(route_name))

    def test_article_sitemap_contains_all_article_details(self):
        response = self.client.get("/sitemap-articles.xml")

        self.assertEqual(response.status_code, 200)
        for article in ARTICLES:
            self.assertIn(
                f"/articles/{article['slug']}/",
                response.content.decode(),
                response.content.decode(),
            )
