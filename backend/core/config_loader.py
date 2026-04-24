from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Load simulator configuration from YAML files."""

    REQUIRED_FILES = (
        "users.yaml",
        "projects.yaml",
        "models.yaml",
        "limits.yaml",
        "degradation.yaml",
    )

    def __init__(self, config_dir: str | Path = "config") -> None:
        self.config_dir = Path(config_dir)
        self.configs = self.load_all()

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Load all required configuration files."""
        return {file_name: self._load_yaml(file_name) for file_name in self.REQUIRED_FILES}

    def get_config_summary(self) -> dict[str, object]:
        """Return a compact summary of loaded configuration sections."""
        summary: dict[str, object] = {"config_dir": str(self.config_dir), "files": {}}

        files_summary: dict[str, dict[str, object]] = {}
        for file_name, content in self.configs.items():
            top_level_keys = list(content.keys())
            first_value = next(iter(content.values()), {})
            item_count = len(first_value) if isinstance(first_value, dict) else len(content)
            files_summary[file_name] = {
                "top_level_keys": top_level_keys,
                "item_count": item_count,
            }

        summary["files"] = files_summary
        return summary

    def _load_yaml(self, file_name: str) -> dict[str, Any]:
        path = self.config_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"Required config file not found: {path}")

        try:
            with path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in config file {path}: {exc}") from exc

        if not isinstance(data, dict) or not data:
            raise ValueError(f"Config file must contain a non-empty mapping: {path}")

        return data
