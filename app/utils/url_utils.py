"""URL and domain utilities"""

import re
from urllib.parse import urlparse


def sanitize_domain(client_id: str) -> str:
    """
    Sanitize client_id to extract clean domain name.

    Handles various input formats:
    - "https://google.co.uk" → "google.co.uk"
    - "google.co.uk/" → "google.co.uk"
    - "www.google.co.uk" → "google.co.uk"
    - "http://www.example.com/path" → "example.com"

    Args:
        client_id: Raw client identifier (may include protocol, www, paths, etc.)

    Returns:
        Clean domain name (lowercase, no protocol, no www, no trailing slash)
    """
    if not client_id:
        return ""

    # Trim whitespace
    domain = client_id.strip()

    # If it looks like a URL with protocol, parse it
    if "://" in domain:
        parsed = urlparse(domain)
        domain = parsed.netloc or parsed.path

    # Remove any remaining protocol markers (edge case)
    domain = re.sub(r'^(https?://|//)', '', domain)

    # Remove trailing slashes and paths
    domain = domain.split('/')[0]

    # Remove www. prefix
    if domain.startswith('www.'):
        domain = domain[4:]

    # Remove any port numbers (e.g., example.com:8080 → example.com)
    domain = domain.split(':')[0]

    # Convert to lowercase for consistency
    domain = domain.lower()

    return domain


def ensure_url_with_protocol(domain: str, default_protocol: str = "https") -> str:
    """
    Ensure a domain has a protocol for URL operations.

    Args:
        domain: Domain name (may or may not have protocol)
        default_protocol: Protocol to add if missing (default: "https")

    Returns:
        Full URL with protocol

    Examples:
        "google.com" → "https://google.com"
        "http://google.com" → "http://google.com"
    """
    if not domain:
        return ""

    domain = domain.strip()

    # Already has protocol
    if domain.startswith(('http://', 'https://')):
        return domain

    # Add default protocol
    return f"{default_protocol}://{domain}"
