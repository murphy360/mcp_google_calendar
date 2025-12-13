"""OAuth2 authentication for Google Calendar API."""

import json
import logging
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class CalendarAuth:
    """Handle Google Calendar OAuth2 authentication."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._credentials: Credentials | None = None

    def _ensure_credentials_dir(self) -> None:
        """Ensure credentials directory exists."""
        self.settings.credentials_dir.mkdir(parents=True, exist_ok=True)

    def _create_client_secrets(self) -> None:
        """Create client_secrets.json from environment variables."""
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise ValueError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables are required"
            )

        self._ensure_credentials_dir()

        # Desktop App format (installed application)
        secrets = {
            "installed": {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"],
            }
        }

        with open(self.settings.client_secrets_file, "w") as f:
            json.dump(secrets, f, indent=2)

        logger.info(f"Created client_secrets.json at {self.settings.client_secrets_file}")

    def get_credentials(self) -> Credentials:
        """Get valid OAuth2 credentials, refreshing or creating as needed."""
        if self._credentials and self._credentials.valid:
            return self._credentials

        # Try to load existing token
        if self.settings.token_file.exists():
            self._credentials = Credentials.from_authorized_user_file(
                str(self.settings.token_file), self.settings.oauth_scopes
            )

        # Check if credentials need refresh
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                self._save_credentials()
                logger.info("Refreshed OAuth2 credentials")
                return self._credentials
            except Exception as e:
                logger.warning(f"Failed to refresh credentials: {e}")
                self._credentials = None

        # If still no valid credentials, need to run OAuth flow
        if not self._credentials or not self._credentials.valid:
            self._credentials = self._run_oauth_flow()

        return self._credentials

    def _run_oauth_flow(self) -> Credentials:
        """Run the OAuth2 flow to get new credentials."""
        # Ensure client_secrets.json exists
        if not self.settings.client_secrets_file.exists():
            self._create_client_secrets()

        # Check if running in headless mode
        headless = os.environ.get("HEADLESS", "false").lower() == "true"

        if headless:
            # For headless mode, use out-of-band flow
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.settings.client_secrets_file),
                self.settings.oauth_scopes,
            )

            # Generate authorization URL
            auth_url, _ = flow.authorization_url(prompt="consent")

            print("\n" + "=" * 60)
            print("AUTHORIZATION REQUIRED")
            print("=" * 60)
            print(f"\nPlease visit this URL to authorize:\n\n{auth_url}\n")
            print("After authorization, enter the authorization code below.")
            print("=" * 60 + "\n")

            code = input("Enter authorization code: ").strip()
            flow.fetch_token(code=code)
            credentials = flow.credentials
        else:
            # Normal flow with local server
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.settings.client_secrets_file),
                self.settings.oauth_scopes,
            )
            credentials = flow.run_local_server(port=0)

        self._credentials = credentials
        self._save_credentials()

        logger.info("Successfully obtained new OAuth2 credentials")
        return credentials

    def _save_credentials(self) -> None:
        """Save credentials to token file."""
        if self._credentials:
            self._ensure_credentials_dir()
            with open(self.settings.token_file, "w") as f:
                f.write(self._credentials.to_json())
            logger.info(f"Saved credentials to {self.settings.token_file}")

    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        try:
            creds = self.get_credentials()
            return creds is not None and creds.valid
        except Exception:
            return False


def setup_oauth() -> None:
    """Run OAuth setup from command line."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 60)
    print("Google Calendar MCP Server - OAuth Setup")
    print("=" * 60 + "\n")

    settings = get_settings()

    if not settings.google_client_id or not settings.google_client_secret:
        print("ERROR: Missing Google OAuth credentials!")
        print("\nPlease set the following environment variables:")
        print("  - GOOGLE_CLIENT_ID")
        print("  - GOOGLE_CLIENT_SECRET")
        print("\nYou can get these from the Google Cloud Console:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create or select a project")
        print("  3. Enable the Google Calendar API")
        print("  4. Create OAuth 2.0 credentials (Desktop App type)")
        sys.exit(1)

    auth = CalendarAuth(settings)

    try:
        credentials = auth.get_credentials()
        print("\n✅ Successfully authenticated!")
        print(f"   Token saved to: {settings.token_file}")
        print("\nYou can now start the MCP server.")
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_oauth()
