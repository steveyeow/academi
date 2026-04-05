from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from .text_utils import html_to_plain_text, normalize_text

log = logging.getLogger(__name__)

MAX_FETCH_BYTES = 4 * 1024 * 1024  # match file upload cap (4 MB)
MAX_REDIRECTS = 5
USER_AGENT = "Feynman/1.0 (book import; +https://github.com/steveyeow/feynman)"

_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE | re.DOTALL)


def _is_safe_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if addr.version == 6 and addr.ipv4_mapped is not None:
        return _is_safe_ip(addr.ipv4_mapped)
    if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast:
        return False
    if addr.is_reserved:
        return False
    if getattr(addr, "is_unspecified", False):
        return False
    return True


def _host_resolves_to_safe_ips(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        log.debug("DNS resolve failed for %s: %s", hostname, exc)
        return False
    if not infos:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if not _is_safe_ip(addr):
            return False
    return True


def validate_public_http_url(url: str) -> str:
    """Return normalized URL string or raise ValueError."""
    raw = url.strip()
    if not raw:
        raise ValueError("URL is required")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are supported")
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs with embedded credentials are not allowed")
    host = parsed.hostname
    if not host:
        raise ValueError("Invalid URL")
    host = host.lower()
    # Literal IP in URL
    try:
        addr = ipaddress.ip_address(host)
        if not _is_safe_ip(addr):
            raise ValueError("This URL cannot be imported")
    except ValueError:
        if not _host_resolves_to_safe_ips(host):
            raise ValueError("This host cannot be reached for import")
    # Reconstruct without credentials / fragments
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    else:
        netloc = host
    return urlunparse((parsed.scheme, netloc, parsed.path or "/", "", parsed.query, ""))


def _read_body_limited(response: httpx.Response, max_bytes: int) -> bytes:
    buf = bytearray()
    for chunk in response.iter_bytes(chunk_size=65536):
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise ValueError(f"Page is too large (max {max_bytes // (1024 * 1024)} MB)")
    return bytes(buf)


def fetch_url_body(url: str) -> tuple[bytes, str | None, str]:
    """
    Fetch URL with manual redirects and SSRF checks at each hop.
    Returns (body, content_type without charset, final_url).
    """
    current = validate_public_http_url(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,text/plain,text/markdown;q=0.9,*/*;q=0.5",
    }
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_http_url(current)
        with httpx.Client(timeout=httpx.Timeout(45.0), follow_redirects=False) as client:
            with client.stream("GET", current, headers=headers) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("location")
                    if not loc:
                        raise ValueError("Redirect without Location header")
                    current = urljoin(str(r.request.url), loc.strip())
                    continue
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise ValueError(f"Could not fetch URL (HTTP {r.status_code})") from exc
                ct = r.headers.get("content-type", "")
                content_type = ct.split(";")[0].strip().lower() if ct else None
                body = _read_body_limited(r, MAX_FETCH_BYTES)
                return body, content_type, str(r.url)
    raise ValueError("Too many redirects")


def _looks_like_html(snippet: str) -> bool:
    s = snippet[:4000].lower()
    return "<html" in s or "<body" in s or "<!doctype html" in s


def text_from_fetched_body(body: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "pdf" in ct or body[:4] == b"%PDF":
        raise ValueError("PDF links are not supported — download the file and upload it instead")
    if "epub" in ct:
        raise ValueError("EPUB links are not supported — download the file and upload it instead")

    if "json" in ct and "html" not in ct:
        return normalize_text(body.decode("utf-8", errors="ignore"))

    if "html" in ct or "xml" in ct:
        decoded = body.decode("utf-8", errors="ignore")
        return html_to_plain_text(decoded)

    if ct.startswith("text/") or ct in ("application/octet-stream", "", "application/x-www-form-urlencoded"):
        decoded = body.decode("utf-8", errors="ignore")
        if _looks_like_html(decoded):
            return html_to_plain_text(decoded)
        return normalize_text(decoded)

    # Unknown type: try UTF-8; if it looks like HTML, strip tags
    decoded = body.decode("utf-8", errors="ignore")
    if _looks_like_html(decoded):
        return html_to_plain_text(decoded)
    return normalize_text(decoded)


def suggest_book_name_from_page(html_or_text: str, url: str, final_url: str) -> str:
    """Prefer <title>, else host + path slug."""
    raw = html_or_text[:500_000]
    m = _TITLE_RE.search(raw)
    if m:
        title = normalize_text(m.group(1))
        if len(title) >= 2 and len(title) <= 200:
            return title
    parsed = urlparse(final_url)
    host = (parsed.hostname or "").replace("www.", "")
    path = (parsed.path or "/").strip("/")
    if path:
        segment = path.split("/")[-1].replace("-", " ").replace("_", " ")
        segment = re.sub(r"\.[a-zA-Z0-9]+$", "", segment)
        if segment and len(segment) <= 120:
            return f"{host} — {segment}" if host else segment
    return host or "Imported page"


def fetch_url_as_book_text(url: str) -> tuple[str, str, str]:
    """
    Fetch a public URL and return (plain_text, suggested_book_name, final_url).
    """
    body, content_type, final_url = fetch_url_body(url)
    decoded_preview = body.decode("utf-8", errors="ignore")
    text = text_from_fetched_body(body, content_type)
    if len(text.strip()) < 40:
        raise ValueError(
            "Very little text on this page. Open the page that actually contains the article or transcript, "
            "copy its URL, and try again (site homepages and navigation lists usually don’t work)."
        )
    name = suggest_book_name_from_page(decoded_preview, url, final_url)
    return text, name, final_url
