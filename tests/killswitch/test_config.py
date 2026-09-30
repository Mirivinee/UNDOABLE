from pathlib import Path

from undoable.killswitch.config import KillSwitchConfig, load_config


def test_defaults_when_no_config_file(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config == KillSwitchConfig()
    assert config.max_actions is None
    assert config.loop_threshold == 3


def test_reads_max_actions_and_loop_threshold(tmp_path: Path) -> None:
    config_dir = tmp_path / ".undoable"
    config_dir.mkdir()
    (config_dir / "config.json").write_text('{"max_actions": 50, "loop_threshold": 4}')

    config = load_config(tmp_path)
    assert config.max_actions == 50
    assert config.loop_threshold == 4


def test_malformed_json_falls_back_to_defaults(tmp_path: Path) -> None:
    config_dir = tmp_path / ".undoable"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{not valid json")

    assert load_config(tmp_path) == KillSwitchConfig()


def test_non_dict_json_falls_back_to_defaults(tmp_path: Path) -> None:
    config_dir = tmp_path / ".undoable"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("[1, 2, 3]")

    assert load_config(tmp_path) == KillSwitchConfig()
