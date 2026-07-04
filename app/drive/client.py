import io
import json
import threading

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.drive.models import DriveFile
from app.utils.logging_config import get_logger
from app.utils.retry import with_retry

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/json",
    "text/plain",
}
SUPPORTED_EXTENSIONS = {"pdf", "json"}
FIELDS = "files(id,name,mimeType,modifiedTime,md5Checksum,size),nextPageToken"


class GoogleDriveClient:
    def __init__(self, service_account_json: str, folder_id: str, page_size: int) -> None:
        self._folder_id = folder_id
        self._page_size = page_size
        credentials_info = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=SCOPES
        )
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._lock = threading.Lock()

    def _is_supported(self, name: str, mime_type: str) -> bool:
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        return mime_type in SUPPORTED_MIME_TYPES or extension in SUPPORTED_EXTENSIONS

    @with_retry(max_attempts=3, backoff_seconds=5)
    def list_files(self) -> list[DriveFile]:
        files: list[DriveFile] = []
        skipped_unsupported = 0
        skipped_no_checksum = 0
        raw_count = 0
        page_token: str | None = None
        query = f"'{self._folder_id}' in parents and trashed = false"

        with self._lock:
            while True:
                response = (
                    self._service.files()
                    .list(
                        q=query,
                        fields=FIELDS,
                        pageSize=self._page_size,
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )

                items = response.get("files", [])
                raw_count += len(items)

                for item in items:
                    name = item.get("name", "")
                    mime_type = item.get("mimeType", "")

                    if not self._is_supported(name, mime_type):
                        skipped_unsupported += 1
                        logger.info(
                            "drive_file_skipped_unsupported_type",
                            file_name=name,
                            mime_type=mime_type,
                        )
                        continue

                    if not item.get("md5Checksum"):
                        skipped_no_checksum += 1
                        logger.info(
                            "drive_file_skipped_no_checksum",
                            file_name=name,
                            mime_type=mime_type,
                        )
                        continue

                    files.append(
                        DriveFile(
                            file_id=item["id"],
                            name=name,
                            mime_type=mime_type,
                            modified_time=item["modifiedTime"],
                            md5_checksum=item["md5Checksum"],
                            size=int(item.get("size", 0)),
                        )
                    )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        logger.info(
            "drive_files_listed",
            raw_count=raw_count,
            matched_count=len(files),
            skipped_unsupported=skipped_unsupported,
            skipped_no_checksum=skipped_no_checksum,
            folder_id=self._folder_id,
        )
        return files

    @with_retry(max_attempts=3, backoff_seconds=5)
    def download_file(self, file_id: str) -> bytes:
        with self._lock:
            request = self._service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buffer.getvalue()
