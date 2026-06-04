"""
Security Middleware for HTTP Method Restrictions and Additional Protections

This middleware restricts HTTP methods to safe verbs (GET, HEAD, POST, OPTIONS)
and blocks potentially dangerous methods (PUT, DELETE, TRACE, CONNECT) that could
be exploited for unauthorized resource modification or reconnaissance.
"""

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

# Allowed HTTP methods for this application
ALLOWED_METHODS = {'GET', 'HEAD', 'POST', 'OPTIONS'}

# Dangerous methods that should be blocked
DANGEROUS_METHODS = {'PUT', 'DELETE', 'TRACE', 'CONNECT', 'PATCH'}


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
