from pathlib import Path


def prompt_for_site() -> str:
    while True:
        answer = input("Choose Garmin site [cn/global]: ").strip().lower()
        if answer in {"cn", "global"}:
            return answer
        print("Please enter 'cn' or 'global'.")


def prompt_for_input_dir() -> Path:
    return Path(input("Enter input directory: ").strip()).expanduser().resolve()
