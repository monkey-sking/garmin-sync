from garmin_sync.onedrive_models import OneDriveFolder
from garmin_sync.onedrive_picker import choose_folder


def test_choose_folder_delegates_to_browser_capture():
    calls = {}

    class FakeClient:
        def capture_selected_folder(self, initial_url=None):
            calls["initial_url"] = initial_url
            return OneDriveFolder(
                url="https://onedrive.live.com/?id=%2FWorkouts",
                name="Workouts",
            )

    selected = choose_folder(FakeClient(), initial_url="https://onedrive.live.com/")

    assert selected.url == "https://onedrive.live.com/?id=%2FWorkouts"
    assert selected.name == "Workouts"
    assert calls["initial_url"] == "https://onedrive.live.com/"
