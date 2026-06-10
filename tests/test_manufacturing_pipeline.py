"""Verify manufacturing output files are generated correctly."""
import shutil
from pathlib import Path

import pytest

from ai_probe_router.config import load_config
from ai_probe_router.eda_adapters.kicad.cli_runner import find_kicad_cli
from ai_probe_router.engine import run


def test_manufacturing_files_generated(tmp_path):
    if find_kicad_cli() is None:
        pytest.skip("KiCad CLI not available")
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    config_src = examples / "iot_sensor_node_advanced_config.yaml"
    project_src = examples / "iot_sensor_node_project"
    dev_board = repo_root / "ai_probe_router" / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"

    for f in ["main.kicad_pcb", "main.kicad_sch"]:
        shutil.copy(project_src / f, tmp_path / f)
    shutil.copy(config_src, tmp_path / "config.yaml")
    mcu_profile_src = repo_root / "ai_probe_router" / "libraries" / "mcu_profiles" / "esp32_s3.yaml"
    if mcu_profile_src.exists():
        shutil.copy(mcu_profile_src, tmp_path / "esp32_s3.yaml")

    def _fix_paths(config_path: Path, dev_board_path: Path) -> None:
        text = config_path.read_text(encoding="utf-8")
        text = text.replace(
            "../ai_probe_router/libraries/dev_boards/stm32_nucleo_64.yaml",
            str(dev_board_path).replace("\\", "/"),
        )
        text = text.replace(
            "../ai_probe_router/libraries/mcu_profiles/esp32_s3.yaml",
            "esp32_s3.yaml",
        )
        config_path.write_text(text, encoding="utf-8")

    _fix_paths(tmp_path / "config.yaml", dev_board)

    cfg = load_config(tmp_path / "config.yaml")
    report, _ = run(cfg, tmp_path)

    mfg_dir = tmp_path / "output" / "manufacturing"
    assert mfg_dir.exists(), "Manufacturing directory not created"

    # Gerber files
    gerbers = list(mfg_dir.glob("*.g*"))  # .gtl, .gbl, .gto, .gbo, .gts, .gbs, .gm1
    assert len(gerbers) >= 6, f"Expected at least 6 Gerber files, found {len(gerbers)}"

    # Drill file
    drill_files = list(mfg_dir.glob("*.drl"))
    assert len(drill_files) >= 1, "Drill file not generated"

    # Pick & Place
    pos_files = list(mfg_dir.glob("placement.csv"))
    assert len(pos_files) == 1, "Pick&Place file not generated"
    pos_text = pos_files[0].read_text(encoding="utf-8")
    assert len(pos_text.splitlines()) > 1, "Pick&Place file is empty"

    # Notes confirm exports
    assert any("Gerber" in n for n in report.notes)
    assert any("Drill" in n for n in report.notes)
    assert any("Pick&Place" in n for n in report.notes)
