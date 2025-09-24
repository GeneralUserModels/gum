from __future__ import annotations

import os
import shutil
from typing import Optional

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


def initialize_google_drive(client_secrets_path: Optional[str] = None) -> GoogleDrive:
    """Initialise Google Drive authentication with an optional secrets path."""
    gauth = GoogleAuth()

    if client_secrets_path:
        client_secrets_path = os.path.abspath(os.path.expanduser(client_secrets_path))
        if not os.path.exists(client_secrets_path):
            raise FileNotFoundError(f"Client secrets file not found: {client_secrets_path}")

        temp_client_secrets = "client_secrets.json"
        try:
            shutil.copy2(client_secrets_path, temp_client_secrets)
            gauth.LocalWebserverAuth()
        finally:
            try:
                os.remove(temp_client_secrets)
            except OSError:
                pass
    else:
        gauth.LocalWebserverAuth()

    return GoogleDrive(gauth)


def list_folders(drive: GoogleDrive):
    """List all folders in Google Drive to help find folder IDs."""
    folders = drive.ListFile({'q': "mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
    for folder in folders:
        print(f"Name: {folder['title']}, ID: {folder['id']}")
    return folders


def find_folder_by_name(folder_name: str, drive: GoogleDrive):
    """Find a Google Drive folder by its name and return its identifier."""
    folders = drive.ListFile({'q': f"mimeType='application/vnd.google-apps.folder' and title='{folder_name}' and trashed=false"}).GetList()
    if folders:
        return folders[0]['id']
    return None


def upload_file(path: str, drive_dir: str, drive_instance: GoogleDrive):
    """Upload *path* to Google Drive folder *drive_dir* and remove the local copy."""
    upload_file = drive_instance.CreateFile({
        'title': os.path.basename(path),
        'parents': [{'id': drive_dir}],
    })
    upload_file.SetContentFile(path)
    upload_file.Upload()
    os.remove(path)
