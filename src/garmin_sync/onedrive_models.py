from dataclasses import dataclass


@dataclass(frozen=True)
class OneDriveFolder:
    url: str
    name: str
