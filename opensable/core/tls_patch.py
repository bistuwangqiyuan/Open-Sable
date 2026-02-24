"""
TLS Fingerprint Patch — Makes twikit use curl_cffi instead of httpx.

Problem: twikit uses plain httpx, which has a Python TLS fingerprint (JA3/JA4).
X detects the real platform via TLS fingerprint, TCP stack, etc.
Even with a mobile User-Agent, X sees "Linux desktop" because httpx leaks it.

Solution: Replace httpx.AsyncClient with curl_cffi.AsyncSession that impersonates
Chrome 131 on Android — the TLS handshake will match a real Android Chrome browser.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

CURL_CFFI_AVAILABLE = False
try:
    from curl_cffi.requests import AsyncSession as _CurlAsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    logger.warning("curl_cffi not installed — TLS fingerprint impersonation disabled")

# The impersonation target: Chrome 131 on Android
# This makes the TLS handshake (JA3/JA4) look like a real Android Chrome browser
IMPERSONATE_TARGET = "chrome131_android"


class TwikitCurlSession:
    """
    Drop-in wrapper around curl_cffi.AsyncSession that provides the
    httpx.AsyncClient interface twikit expects.

    Twikit accesses:
      - self.http.request(method, url, headers=..., data=..., **kwargs)
      - self.http.cookies          (.jar, .clear(), .update(), .get(), dict())
      - self.http.cookies.jar      (iterable of cookie objects)
      - self.http._mounts          (proxy getter/setter — we stub this)
      - self.http.headers           (dict-like)
    """

    def __init__(self, proxy: Optional[str] = None, **kwargs):
        # Build curl_cffi session with Android Chrome TLS fingerprint
        session_kwargs = {
            "impersonate": IMPERSONATE_TARGET,
        }
        if proxy:
            session_kwargs["proxies"] = {"https": proxy, "http": proxy}

        self._session = _CurlAsyncSession(**session_kwargs)

        # Stub _mounts so twikit's proxy getter/setter doesn't crash
        self._mounts = {}

        # Expose headers dict for compatibility
        self.headers = self._session.headers if hasattr(self._session, 'headers') else {}

        logger.info(f"🛡️ TLS patch active: impersonating {IMPERSONATE_TARGET}")

    @property
    def cookies(self):
        """Expose curl_cffi cookies — compatible with twikit's usage."""
        return self._session.cookies

    @cookies.setter
    def cookies(self, value):
        """Twikit does self.http.cookies = list(cookies.items())"""
        self._session.cookies.clear()
        if isinstance(value, list):
            for name, val in value:
                self._session.cookies.set(name, val)
        elif isinstance(value, dict):
            self._session.cookies.update(value)
        else:
            # Try to iterate as key-value pairs
            try:
                for name, val in value:
                    self._session.cookies.set(name, val)
            except (TypeError, ValueError):
                pass

    async def request(self, method: str, url: str, **kwargs) -> "TwikitCurlResponse":
        """
        Forward request to curl_cffi session.
        Maps httpx-style kwargs to curl_cffi equivalents.
        """
        # curl_cffi uses 'content' instead of 'data' for bytes in some cases,
        # but 'data' is also supported. Just pass through.
        response = await self._session.request(method, url, **kwargs)
        return TwikitCurlResponse(response)

    async def aclose(self):
        """Clean up session."""
        try:
            await self._session.close()
        except Exception:
            pass


class TwikitCurlResponse:
    """
    Wraps curl_cffi Response to match httpx.Response interface.
    Twikit accesses: .json(), .text, .content, .status_code, .headers
    """

    def __init__(self, response):
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def text(self) -> str:
        return self._response.text

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def headers(self):
        return self._response.headers

    def json(self, **kwargs):
        return self._response.json(**kwargs)


def patch_twikit_client(client, proxy: Optional[str] = None):
    """
    Replaces a twikit Client's httpx backend with curl_cffi
    for Android Chrome TLS fingerprint impersonation.

    Call this AFTER creating the twikit Client but BEFORE making requests.

    Args:
        client: twikit.Client instance
        proxy: Optional proxy URL
    """
    if not CURL_CFFI_AVAILABLE:
        logger.warning("curl_cffi not available — skipping TLS patch")
        return False

    try:
        old_http = client.http
        new_http = TwikitCurlSession(proxy=proxy)

        # Copy existing cookies from the old session
        try:
            old_cookies = dict(old_http.cookies)
            if old_cookies:
                new_http.cookies.update(old_cookies)
        except Exception:
            pass

        # Replace the HTTP backend
        client.http = new_http

        # Reset client_transaction so it re-inits with the new session
        if hasattr(client, 'client_transaction'):
            client.client_transaction.home_page_response = None

        logger.info("✅ TLS patch applied — twikit now uses Chrome Android fingerprint")
        return True

    except Exception as e:
        logger.error(f"❌ TLS patch failed: {e}")
        return False
