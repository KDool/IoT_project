import json
from pathlib import Path


def load_config(config_path: Path | None = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "configuration.json"

    with open(config_path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


config = load_config()
