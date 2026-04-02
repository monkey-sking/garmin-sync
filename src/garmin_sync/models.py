from dataclasses import asdict
from dataclasses import dataclass
from typing import Optional


@dataclass
class UploadRecord:
    site: str
    sha256: str
    file_path: str
    file_name: str
    status: str = "pending"
    first_seen_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
