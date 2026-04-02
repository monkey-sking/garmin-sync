from garmin_sync.sites.base import GarminSiteAdapter


class GarminGlobalAdapter(GarminSiteAdapter):
    def __init__(self) -> None:
        super().__init__(
            key="global",
            label="Garmin Global",
            import_url="https://connect.garmin.com/modern/import-data",
            file_input_selectors=(
                "input[type='file']",
                "input[accept*='.fit']",
            ),
            submit_button_selectors=(
                "button:has-text('Import Data')",
                "button:has-text('Import')",
                "[role='button']:has-text('Import Data')",
                "[role='button']:has-text('Import')",
            ),
            success_markers=("success", "completed", "imported", "done"),
            duplicate_markers=("duplicate", "already exists", "already uploaded"),
            failure_markers=("failed", "error", "try again"),
        )
