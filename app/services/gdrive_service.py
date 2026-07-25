# app/services/gdrive_service.py
"""Direct-to-Google-Drive backup sync, as an alternative to the folder-based
sync (which relies on a desktop Drive/Dropbox client watching a local
folder). This talks to the Drive API directly via OAuth, using the
`drive.file` scope — the app can only see/manage files it created itself,
never the rest of the user's Drive.

Requires: google-auth, google-auth-oauthlib, google-api-python-client
    pip install google-auth google-auth-oauthlib google-api-python-client

Setup (one-time, per deployment):
    1. Go to https://console.cloud.google.com/apis/credentials
    2. Create an OAuth 2.0 Client ID of type "Web application"
    3. Add an Authorized redirect URI of:
           http://localhost:<port>/api/gdrive/oauth-callback
       (use the same port this app is configured to run on)
    4. Enable the "Google Drive API" for the project
    5. Paste the resulting Client ID + Client Secret into the app's
       Backup & Sync tab (Root only) and click "Connect Google Drive".
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from app.config import BASE_DIR, load_config
from app.database import get_connection
from app.repositories.settings_repository import SettingsRepository
from app.services.backup_service import BackupService

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_FOLDER_NAME = "AttendancePC Backups"
DRIVE_RETENTION = 5


class GDriveNotConfigured(Exception):
    """Raised when client credentials or a connected account are missing."""


def _redirect_uri() -> str:
    config = load_config()
    return f"http://localhost:{config['port']}/api/gdrive/oauth-callback"


def _client_config(client_id: str, client_secret: str) -> dict:
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_redirect_uri()],
        }
    }


class GDriveService:
    @staticmethod
    def _settings() -> tuple[str, str, str, str]:
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            return (
                repo.get("gdrive_client_id", ""),
                repo.get("gdrive_client_secret", ""),
                repo.get("gdrive_token", ""),
                repo.get("gdrive_folder_id", ""),
            )

    @staticmethod
    def set_client_credentials(client_id: str, client_secret: str) -> None:
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("gdrive_client_id", client_id.strip())
            repo.set("gdrive_client_secret", client_secret.strip())

    @staticmethod
    def status() -> dict:
        client_id, client_secret, token_json, _ = GDriveService._settings()
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            last_push = repo.get("last_gdrive_push_at", "")
            last_pull = repo.get("last_gdrive_pull_at", "")
        return {
            "configured": bool(client_id and client_secret),
            "connected": bool(token_json),
            "last_push_at": last_push,
            "last_pull_at": last_pull,
        }

    @staticmethod
    def start_auth() -> str:
        """Builds the Google consent-screen URL. Called by an already
        logged-in root user; they open the URL in a browser tab and Google
        redirects back to this app's own callback route."""
        client_id, client_secret, _, _ = GDriveService._settings()
        if not client_id or not client_secret:
            raise GDriveNotConfigured("Add a Google OAuth client ID and secret first.")

        flow = Flow.from_client_config(
            _client_config(client_id, client_secret), scopes=SCOPES, redirect_uri=_redirect_uri()
        )
        state = secrets.token_urlsafe(16)
        auth_url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent", state=state,
        )
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("gdrive_oauth_state", state)
        return auth_url

    @staticmethod
    def finish_auth(code: str, state: str) -> None:
        """Exchanges the authorization code for tokens. The `state` value
        is our only protection here since Google's redirect carries no
        session cookie — it must match what start_auth() minted."""
        client_id, client_secret, _, _ = GDriveService._settings()
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            expected_state = repo.get("gdrive_oauth_state", "")

        if not state or not expected_state or state != expected_state:
            raise ValueError("OAuth state mismatch — please try connecting again.")

        flow = Flow.from_client_config(
            _client_config(client_id, client_secret), scopes=SCOPES, redirect_uri=_redirect_uri()
        )
        flow.fetch_token(code=code)
        creds = flow.credentials

        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("gdrive_token", creds.to_json())
            repo.set("gdrive_oauth_state", "")

    @staticmethod
    def disconnect() -> None:
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("gdrive_token", "")
            repo.set("gdrive_folder_id", "")

    @staticmethod
    def _client():
        _, _, token_json, _ = GDriveService._settings()
        if not token_json:
            raise GDriveNotConfigured("Google Drive is not connected yet.")

        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with get_connection() as conn:
                repo = SettingsRepository(conn)
                repo.set("gdrive_token", creds.to_json())

        return build("drive", "v3", credentials=creds)

    @staticmethod
    def _ensure_folder(drive) -> str:
        _, _, _, folder_id = GDriveService._settings()
        if folder_id:
            try:
                drive.files().get(fileId=folder_id, fields="id, trashed").execute()
                return folder_id
            except Exception:
                pass  # folder was deleted/trashed remotely; fall through and recreate

        results = drive.files().list(
            q=f"name = '{DRIVE_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            spaces="drive", fields="files(id, name)",
        ).execute()
        files = results.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            metadata = {"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
            folder = drive.files().create(body=metadata, fields="id").execute()
            folder_id = folder["id"]

        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("gdrive_folder_id", folder_id)
        return folder_id

    @staticmethod
    def push() -> dict:
        """Uploads a fresh export bundle (DB + photos + uploads) straight to
        Google Drive, reusing the same validated export used by the manual
        .zip download and by folder-based sync."""
        drive = GDriveService._client()
        folder_id = GDriveService._ensure_folder(drive)

        zip_path = BackupService.export_package()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        drive_name = f"sync_{ts}.zip"

        media = MediaFileUpload(str(zip_path), mimetype="application/zip", resumable=True)
        metadata = {"name": drive_name, "parents": [folder_id]}
        drive.files().create(body=metadata, media_body=media, fields="id").execute()

        # Bound how many bundles live in Drive at once, same idea as the
        # local sync-folder / backups-dir retention.
        existing = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces="drive", fields="files(id, name, createdTime)",
            orderBy="createdTime desc",
        ).execute().get("files", [])
        for stale in existing[DRIVE_RETENTION:]:
            try:
                drive.files().delete(fileId=stale["id"]).execute()
            except Exception:
                pass

        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("last_gdrive_push_at", datetime.now().isoformat())

        return {"success": True, "uploaded": drive_name}

    @staticmethod
    def pull() -> dict:
        """Downloads the newest bundle from Drive and imports it through the
        same validated import path used everywhere else (integrity check +
        pre-import rollback snapshot + non-destructive photo merge)."""
        drive = GDriveService._client()
        folder_id = GDriveService._ensure_folder(drive)

        files = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces="drive", fields="files(id, name, createdTime)",
            orderBy="createdTime desc", pageSize=1,
        ).execute().get("files", [])

        if not files:
            return {"success": True, "imported": False, "message": "Nothing in Drive yet."}

        newest = files[0]
        request = drive.files().get_media(fileId=newest["id"])

        tmp_path = BASE_DIR / "temp_gdrive_download.zip"
        with open(tmp_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        try:
            BackupService.import_package(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("last_gdrive_pull_at", datetime.now().isoformat())

        return {"success": True, "imported": True, "from": newest["name"]}