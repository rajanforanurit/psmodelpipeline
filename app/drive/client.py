import io
import json

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

    @with_retry(max_attempts=3, backoff_seconds=5)
    def list_files(self) -> list[DriveFile]:
        files: list[DriveFile] = []
        page_token: str | None = None
        query = f"'{self._folder_id}' in parents and trashed = false"

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

            for item in response.get("files", []):
                mime_type = item.get("mimeType", "")
                if mime_type not in SUPPORTED_MIME_TYPES:
                    continue
                if not item.get("md5Checksum"):
                    continue
                files.append(
                    DriveFile(
                        file_id=item["id"],
                        name=item["name"],
                        mime_type=mime_type,
                        modified_time=item["modifiedTime"],
                        md5_checksum=item["md5Checksum"],
                        size=int(item.get("size", 0)),
                    )
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        logger.info("drive_files_listed", count=len(files))
        return files

    @with_retry(max_attempts=3, backoff_seconds=5)
    def download_file(self, file_id: str) -> bytes:
        request = self._service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()
