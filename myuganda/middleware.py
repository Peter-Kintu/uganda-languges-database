"""
Security Middleware for HTTP Method Restrictions and Additional Protections

This middleware restricts HTTP methods to safe verbs (GET, HEAD, POST, OPTIONS)
and blocks potentially dangerous methods (PUT, DELETE, TRACE, CONNECT) that could
be exploited for unauthorized resource modification or reconnaissance.

It also short-circuits obvious WordPress-style reconnaissance probes such as
/wp-json, /wp-admin/install.php, /xmlrpc.php, /wp-includes/wlwmanifest.xml,
and rest_route payloads, returning a clean 404 before the request reaches
Django URL resolution.
"""

import logging
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseNotFound, HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

THROTTLED_PATHS = {
    '/hotel/': {'limit': 25, 'window': 60},
    '/hotel/social_feed': {'limit': 25, 'window': 60},
    '/social/feed/': {'limit': 30, 'window': 60},
    '/languages/jobs/': {'limit': 20, 'window': 60},
    '/languages/': {'limit': 25, 'window': 60},
    '/login/': {'limit': 8, 'window': 300},
    '/register/': {'limit': 8, 'window': 300},
    '/social/publish/': {'limit': 6, 'window': 300},
    '/hotel/create_post/': {'limit': 6, 'window': 300},
    '/hotel/post/': {'limit': 6, 'window': 300},
    '/upload/': {'limit': 6, 'window': 300},
}

# Allowed HTTP methods for this application
ALLOWED_METHODS = {'GET', 'HEAD', 'POST', 'OPTIONS'}

# Dangerous methods that should be blocked
DANGEROUS_METHODS = {'PUT', 'DELETE', 'TRACE', 'CONNECT', 'PATCH'}


class CanonicalDomainMiddleware(MiddlewareMixin):
    """Redirect apex domain traffic to the canonical www host while preserving path/query strings."""

    def process_request(self, request):
        host = request.get_host().split(':')[0]
        if host == 'africanaai.info' and request.path not in ['/ads.txt', '/robots.txt']:
            return HttpResponsePermanentRedirect(
                f'https://www.africanaai.info{request.get_full_path()}'
            )
        return None


class WordPressProbeBlockMiddleware(MiddlewareMixin):
    """
    Return a clean 404 for WordPress-style reconnaissance probes aimed at this
    application. These requests are not part of the site API surface and should
    never reach the normal Django URL machinery.
    """

    WP_PATH_PATTERN = re.compile(
        r"(?:/wp-json/|/wp-json$|/wp-admin/|/wp-login\.php|/xmlrpc\.php|/wp-includes/|/wp-content/plugins/|/wlwmanifest\.xml|/wp-admin/install\.php)",
        re.IGNORECASE,
    )

    REST_ROUTE_PATTERN = re.compile(
        r"(?:\/wp\/v2|\/wp\/v2\/|\/batch\/v1|wp-json|wp\/v2|rest_route)",
        re.IGNORECASE,
    )

    def process_request(self, request):
        path = request.path.lower()
        query = request.META.get('QUERY_STRING', '').lower()
        decoded_rest_route = request.GET.get('rest_route', '') if hasattr(request, 'GET') else ''
        decoded_rest_route = decoded_rest_route.lower()
        full_probe = f"{path}?{query}".lower()

        # Explicitly deny obvious WP API / XMLRPC / plugin / manifest style probes.
        if (
            self.WP_PATH_PATTERN.search(path)
            or self.REST_ROUTE_PATTERN.search(query)
            or self.REST_ROUTE_PATTERN.search(full_probe)
            or self.REST_ROUTE_PATTERN.search(decoded_rest_route)
        ):
            logger.warning(
                "Blocked WordPress probe from %s to %s%s",
                request.META.get('REMOTE_ADDR'),
                request.path,
                ('?' + request.META.get('QUERY_STRING', '')) if request.META.get('QUERY_STRING') else '',
            )
            return HttpResponseNotFound("Not Found")

        return None


class HTTPMethodSecurityMiddleware(MiddlewareMixin):
    """
    Restricts HTTP methods to only those required by the application.
    
    Blocks:
    - PUT: Prevents uploading arbitrary files
    - DELETE: Prevents deletion of critical resources
    - TRACE: Prevents HTTP trace attacks that reveal headers
    - CONNECT: Prevents tunneling attacks
    - PATCH: Optional - blocks partial updates if not needed
    
    Returns 405 Method Not Allowed for blocked methods.
    """
    
    def process_request(self, request):
        """Check HTTP method before processing request"""
        
        method = request.method.upper()
        
        # Block dangerous methods
        if method in DANGEROUS_METHODS:
            logger.warning(
                f"Blocked HTTP method '{method}' from {request.META.get('REMOTE_ADDR')} "
                f"to {request.path}. This may indicate an attack attempt."
            )
            
            # Return 405 Method Not Allowed
            response = HttpResponse(
                "405 Method Not Allowed\n\n"
                f"The HTTP method {method} is not allowed on this server.",
                status=405,
                content_type='text/plain'
            )
            
            # Set Allow header to indicate which methods are permitted
            response['Allow'] = ', '.join(sorted(ALLOWED_METHODS))
            
            return response
        
        # Allow all other methods (they will be handled by Django views)
        # Returning None means "continue processing"
        return None


class RateLimitMiddleware(MiddlewareMixin):
    """Simple IP + user rate limiter for public, high-traffic endpoints."""

    def process_request(self, request):
        if request.method not in {'GET', 'POST', 'HEAD'}:
            return None

        path = request.path or '/'
        if path.startswith('/admin/') or path.startswith('/static/') or path.startswith('/media/'):
            return None

        limit = getattr(settings, 'RATE_LIMIT_REQUESTS_PER_MINUTE', 120)
        window = getattr(settings, 'RATE_LIMIT_WINDOW_SECONDS', 60)
        burst = getattr(settings, 'RATE_LIMIT_BURST', 30)

        matching_rule = None
        for known_path, rule in THROTTLED_PATHS.items():
            if path == known_path or path.startswith(known_path):
                matching_rule = rule
                break

        if matching_rule:
            limit = matching_rule['limit']
            window = matching_rule['window']
            burst = min(burst, max(5, int(limit * 0.25)))

        now = int(time.time())
        if request.user.is_authenticated:
            key_base = f"ratelimit:user:{request.user.id}"
        else:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'unknown')).split(',')[0].strip()
            key_base = f"ratelimit:ip:{ip}"

        bucket_key = f"{key_base}:{path}"
        window_key = f"{bucket_key}:window"

        current_window = cache.get(window_key)
        if current_window is None:
            current_window = now
            cache.set(window_key, current_window, timeout=window)

        request_count = cache.get(f"{bucket_key}:{current_window}", 0)
        effective_limit = max(10, limit - burst)
        if request_count >= effective_limit:
            response = HttpResponse(
                "Too many requests. Please slow down and try again shortly.",
                status=429,
                content_type='text/plain',
            )
            response['Retry-After'] = str(window)
            response['X-RateLimit-Limit'] = str(effective_limit)
            response['X-RateLimit-Remaining'] = '0'
            return response

        cache.set(f"{bucket_key}:{current_window}", request_count + 1, timeout=window)
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Adds additional security headers that may not be covered by Django settings.
    
    Headers Added:
    - Permissions-Policy: Controls access to sensitive browser features
    - X-Content-Type-Options: Prevents MIME-type sniffing
    """
    
    def process_response(self, request, response):
        """Add security headers to response"""
        
        # Permissions-Policy: Restrict access to sensitive browser features
        # This prevents attackers from exploiting camera, microphone, geolocation, etc.
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), payment=()'
        )
        
        # X-Content-Type-Options: Prevent browsers from MIME-sniffing
        # Already set by Django's SECURE_CONTENT_TYPE_NOSNIFF, but explicitly included
        if 'X-Content-Type-Options' not in response:
            response['X-Content-Type-Options'] = 'nosniff'
        
        # X-Frame-Options: Prevent clickjacking
        # Already set by Django's X_FRAME_OPTIONS, but explicitly included
        if 'X-Frame-Options' not in response:
            response['X-Frame-Options'] = 'SAMEORIGIN'
        
        # X-XSS-Protection: Deprecated but useful for legacy browsers
        response['X-XSS-Protection'] = '1; mode=block'
        
        return response
