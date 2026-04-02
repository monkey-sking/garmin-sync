import argparse
from pathlib import Path

from garmin_sync.config import ConfigStore
from garmin_sync.config import resolve_input_dir
from garmin_sync.config import resolve_site
from garmin_sync.onedrive_auth import OneDriveAuth
from garmin_sync.onedrive_client import OneDriveClient
from garmin_sync.onedrive_picker import choose_folder
from garmin_sync.onedrive_state import OneDriveStateStore
from garmin_sync.onedrive_sync import pull_fit_files
from garmin_sync.paths import get_app_data_dir
from garmin_sync.uploader import run_login
from garmin_sync.uploader import run_upload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="garmin-sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload_parser = subparsers.add_parser("upload")
    upload_parser.add_argument("directory", nargs="?", type=Path)
    upload_parser.add_argument("--site", choices=["cn", "global"])

    login_parser = subparsers.add_parser("login")
    login_parser.add_argument("--site", choices=["cn", "global"])

    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show")

    set_site_parser = config_subparsers.add_parser("set-default-site")
    set_site_parser.add_argument("site", choices=["cn", "global"])

    set_dir_parser = config_subparsers.add_parser("set-default-dir")
    set_dir_parser.add_argument("directory", type=Path)

    onedrive_parser = subparsers.add_parser("onedrive")
    onedrive_subparsers = onedrive_parser.add_subparsers(dest="onedrive_command", required=True)
    onedrive_subparsers.add_parser("login")
    onedrive_subparsers.add_parser("pick-folder")
    onedrive_subparsers.add_parser("show-folder")
    pull_parser = onedrive_subparsers.add_parser("pull-fit")
    pull_parser.add_argument("--dir", dest="directory", type=Path)
    return parser


def get_data_dir() -> Path:
    return get_app_data_dir()


def handle_config(args: argparse.Namespace, config_store: ConfigStore) -> int:
    config = config_store.load()

    if args.config_command == "show":
        print(f"default_site: {config.default_site}")
        print(f"default_input_dir: {config.default_input_dir}")
        print(f"headless: {config.headless}")
        return 0

    if args.config_command == "set-default-site":
        config.default_site = args.site
    elif args.config_command == "set-default-dir":
        config.default_input_dir = str(args.directory.expanduser().resolve())

    config_store.save(config)
    print("Configuration updated.")
    return 0


def handle_login(args: argparse.Namespace, config_store: ConfigStore) -> int:
    config = config_store.load()
    site = resolve_site(args.site, config)
    run_login(site=site, data_dir=get_data_dir(), headless=config.headless)
    print(f"Saved login session for {site}.")
    return 0


def handle_upload(args: argparse.Namespace, config_store: ConfigStore) -> int:
    config = config_store.load()
    site = resolve_site(args.site, config)
    directory = resolve_input_dir(str(args.directory) if args.directory else None, config)
    summary = run_upload(site=site, directory=directory, data_dir=get_data_dir(), headless=config.headless)
    print(summary.render())
    return 0 if summary.failed_count == 0 else 1


def handle_onedrive(args: argparse.Namespace, config_store: ConfigStore) -> int:
    config = config_store.load()
    data_dir = get_data_dir()
    auth = OneDriveAuth(data_dir)

    if args.onedrive_command == "login":
        auth.login(headless=config.headless)
        config.onedrive_provider = "personal-web"
        config_store.save(config)
        print("OneDrive login saved.")
        return 0

    if args.onedrive_command == "show-folder":
        if not config.onedrive_selected_folder_url:
            raise RuntimeError("No OneDrive folder selected. Run 'garmin-sync onedrive pick-folder' first.")
        print(f"{config.onedrive_selected_folder_name} ({config.onedrive_selected_folder_url})")
        return 0

    client = OneDriveClient(auth, headless=config.headless)

    if args.onedrive_command == "pick-folder":
        selected = choose_folder(client, initial_url=config.onedrive_selected_folder_url)
        config.onedrive_provider = "personal-web"
        config.onedrive_selected_folder_url = selected.url
        config.onedrive_selected_folder_name = selected.name
        config_store.save(config)
        print(f"Selected OneDrive folder: {selected.name} ({selected.url})")
        return 0

    if args.onedrive_command == "pull-fit":
        if not config.onedrive_selected_folder_url:
            raise RuntimeError("No OneDrive folder selected. Run 'garmin-sync onedrive pick-folder' first.")
        download_dir = _resolve_onedrive_download_dir(args.directory, config)
        state_store = OneDriveStateStore(data_dir)
        summary = pull_fit_files(
            client=client,
            folder_url=config.onedrive_selected_folder_url,
            folder_name=config.onedrive_selected_folder_name or "Selected Folder",
            download_dir=download_dir,
            state_store=state_store,
            retry_limit=2,
        )
        config.onedrive_download_dir = str(download_dir)
        config_store.save(config)
        print(summary.render())
        return 0 if summary.failed_count == 0 else 1

    return 0


def _resolve_onedrive_download_dir(cli_dir: Path | None, config) -> Path:
    if cli_dir:
        path = cli_dir.expanduser().resolve()
    elif config.onedrive_download_dir:
        path = Path(config.onedrive_download_dir).expanduser().resolve()
    else:
        path = Path(input("Enter local download directory: ").strip()).expanduser().resolve()

    path.mkdir(parents=True, exist_ok=True)
    return path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config_store = ConfigStore(get_data_dir())

    if args.command == "config":
        return handle_config(args, config_store)
    if args.command == "login":
        return handle_login(args, config_store)
    if args.command == "upload":
        return handle_upload(args, config_store)
    if args.command == "onedrive":
        return handle_onedrive(args, config_store)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
