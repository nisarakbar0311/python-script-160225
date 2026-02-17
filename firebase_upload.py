"""
Upload generated MHRA JSON files to Firebase Storage.
Requires firebase-admin and a service account key (see README).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import config


def _get_bucket(bucket_name: str, credentials_path: Optional[str] = None):
    import firebase_admin
    from firebase_admin import credentials, storage

    try:
        firebase_admin.get_app()
    except ValueError:
        if credentials_path:
            cred = credentials.Certificate(credentials_path)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
    return storage.bucket(bucket_name)


def upload_generated_files(
    *,
    latest_path: Path,
    version_label: str,
    bucket_name: str,
    storage_prefix: str = "mhra",
    credentials_path: Optional[str] = None,
) -> None:
    """
    Upload all generated JSON files to Firebase Storage.
    - Latest copies under `{storage_prefix}/latest/`
    - Versioned copies under `{storage_prefix}/{version_label}/`
    """
    bucket = _get_bucket(bucket_name, credentials_path)
    filenames = list(config.GENERATED_FILES.values())
    version_folder = version_label.replace("/", "_")

    for filename in filenames:
        local_file = latest_path / filename
        if not local_file.exists():
            continue
        content_type = "application/json"
        # Latest (overwriting)
        latest_blob_path = f"{storage_prefix}/latest/{filename}"
        blob = bucket.blob(latest_blob_path)
        blob.upload_from_filename(str(local_file), content_type=content_type)
        # Versioned snapshot
        version_blob_path = f"{storage_prefix}/{version_folder}/{filename}"
        version_blob = bucket.blob(version_blob_path)
        version_blob.upload_from_filename(str(local_file), content_type=content_type)
