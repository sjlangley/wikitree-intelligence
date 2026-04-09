"""WikiTree API client for authentication and profile access."""

import asyncio
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

WIKITREE_API_URL = "https://api.wikitree.com/api.php"
DEFAULT_TIMEOUT = 30.0


class WikiTreeAPIError(Exception):
    """WikiTree API error."""

    pass


class WikiTreeClient:
    """Client for WikiTree API interactions.

    Handles authentication flow, session validation, and profile access.
    """

    def __init__(
        self,
        app_id: str = "WikiTreeIntelligence",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """Initialize WikiTree client.

        Args:
            app_id: Application identifier for WikiTree API
            timeout: HTTP request timeout in seconds
        """
        self.app_id = app_id
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WikiTreeClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_login_url(self, return_url: str) -> str:
        """Generate WikiTree login URL for browser redirect.

        Args:
            return_url: URL to redirect user after successful login

        Returns:
            WikiTree login URL with encoded return_url
        """
        params = {
            "action": "clientLogin",
            "returnURL": return_url,
        }
        return f"{WIKITREE_API_URL}?{urlencode(params)}"

    def get_logout_url(self, return_url: str) -> str:
        """Generate WikiTree logout URL for browser redirect.

        Args:
            return_url: URL to redirect user after logout

        Returns:
            WikiTree logout URL
        """
        params = {
            "action": "clientLogin",
            "doLogout": "1",
            "returnURL": return_url,
        }
        return f"{WIKITREE_API_URL}?{urlencode(params)}"

    async def validate_authcode(
        self, authcode: str
    ) -> dict[str, Any]:
        """Validate auth code and retrieve user information.

        Args:
            authcode: Auth code received from WikiTree redirect

        Returns:
            User information dict with user_id and user_name

        Raises:
            WikiTreeAPIError: If authcode validation fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        params = {
            "action": "clientLogin",
            "authcode": authcode,
            "appId": self.app_id,
        }

        try:
            response = await self._client.post(WIKITREE_API_URL, data=params)
            response.raise_for_status()
            data = response.json()

            client_login = data.get("clientLogin", {})
            result = client_login.get("result")

            if result == "success":
                return {
                    "user_id": client_login.get("user_id"),
                    "user_name": client_login.get("user_name"),
                    "wikitree_id": client_login.get("user_name"),  # WikiTree ID
                }
            else:
                error_msg = client_login.get("error", "Unknown error")
                logger.error(f"WikiTree authcode validation failed: {error_msg}")
                raise WikiTreeAPIError(f"Authcode validation failed: {error_msg}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during authcode validation: {e}")
            raise WikiTreeAPIError(f"HTTP error: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid response format: {e}")
            raise WikiTreeAPIError(f"Invalid API response: {e}")

    async def check_login_status(self, user_id: int) -> bool:
        """Check if a user is still logged in.

        Args:
            user_id: WikiTree user ID to check

        Returns:
            True if user is logged in, False otherwise
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        params = {
            "action": "clientLogin",
            "checkLogin": str(user_id),
            "appId": self.app_id,
        }

        try:
            response = await self._client.post(WIKITREE_API_URL, data=params)
            response.raise_for_status()
            data = response.json()

            client_login = data.get("clientLogin", {})
            result = client_login.get("result")

            return result == "ok"

        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning(f"Error checking login status: {e}")
            return False

    async def get_profile(
        self,
        wikitree_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get a WikiTree profile.

        Args:
            wikitree_id: WikiTree ID (e.g., "Clemens-1")
            fields: Optional list of fields to retrieve

        Returns:
            Profile data dict

        Raises:
            WikiTreeAPIError: If profile retrieval fails

        Note:
            For private profiles, this requires the user to have authenticated
            and have the profile on their trusted list. The session cookies
            must be passed from the browser.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        params: dict[str, Any] = {
            "action": "getProfile",
            "key": wikitree_id,
            "appId": self.app_id,
        }

        if fields:
            params["fields"] = ",".join(fields)

        try:
            response = await self._client.post(WIKITREE_API_URL, data=params)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                profile_data = data[0]
                if profile_data.get("status") == 0:
                    return profile_data
                else:
                    error_msg = profile_data.get("status", "Unknown error")
                    raise WikiTreeAPIError(f"Profile retrieval failed: {error_msg}")
            else:
                raise WikiTreeAPIError("Invalid response format")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during profile retrieval: {e}")
            raise WikiTreeAPIError(f"HTTP error: {e}")
        except (KeyError, ValueError, IndexError) as e:
            logger.error(f"Invalid response format: {e}")
            raise WikiTreeAPIError(f"Invalid API response: {e}")
