from garmin_sync.onedrive_models import OneDriveFolder


def choose_folder(client, initial_url: str | None = None) -> OneDriveFolder:
    return client.capture_selected_folder(initial_url=initial_url)
