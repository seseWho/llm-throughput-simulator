from backend.core.config_loader import ConfigLoader


def test_config_loader_loads_yaml_files_and_returns_summary() -> None:
    loader = ConfigLoader()

    summary = loader.get_config_summary()

    assert summary
    assert "files" in summary
    assert summary["files"]
    assert "users.yaml" in summary["files"]
    assert "projects.yaml" in summary["files"]
    assert "models.yaml" in summary["files"]
    assert "limits.yaml" in summary["files"]
    assert "degradation.yaml" in summary["files"]
