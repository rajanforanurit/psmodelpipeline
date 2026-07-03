from pydantic import BaseModel


class DriveFile(BaseModel):
    file_id: str
    name: str
    mime_type: str
    modified_time: str
    md5_checksum: str
    size: int = 0

    @property
    def extension(self) -> str:
        return self.name.rsplit(".", 1)[-1].lower() if "." in self.name else ""
