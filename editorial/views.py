from django.http import Http404
from django.shortcuts import render

from .content import ARTICLES, ARTICLE_BY_SLUG


def article_index(request):
    return render(request, "editorial/article_index.html", {"articles": ARTICLES})


def article_detail(request, slug):
    article = ARTICLE_BY_SLUG.get(slug)
    if article is None:
        raise Http404("Article not found")
    return render(request, "editorial/article_detail.html", {"article": article})


def privacy_policy(request):
    return render(request, "editorial/privacy_policy.html")


def terms_of_use(request):
    return render(request, "editorial/terms_of_use.html")
