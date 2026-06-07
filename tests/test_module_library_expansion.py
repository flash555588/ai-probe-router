"""Verify expanded module library loads and integrates correctly."""

from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.engine import run
from ai_probe_router.models.module import parse_functional_module


def test_wifi_module_parsing():
    src = Path("libraries/modules/communication/wifi_interface.yaml")
    assert src.exists()
    mod = parse_functional_module({"name": "wifi_test", "type": "wifi_interface"})
    assert mod.name == "wifi_test"
    assert mod.type == "wifi_interface"


def test_lora_module_parsing():
    src = Path("libraries/modules/communication/lora_interface.yaml")
    assert src.exists()
    mod = parse_functional_module({"name": "lora_test", "type": "lora_interface"})
    assert mod.type == "lora_interface"


def test_gnss_module_parsing():
    src = Path("libraries/modules/communication/gnss_module.yaml")
    assert src.exists()
    mod = parse_functional_module({"name": "gnss_test", "type": "gnss_module"})
    assert mod.type == "gnss_module"


def test_motor_driver_module_parsing():
    src = Path("libraries/modules/power/motor_driver.yaml")
    assert src.exists()
    mod = parse_functional_module({"name": "motor_test", "type": "motor_driver"})
    assert mod.type == "motor_driver"


def test_usb_c_pd_module_parsing():
    src = Path("libraries/modules/power/usb_c_pd.yaml")
    assert src.exists()
    mod = parse_functional_module({"name": "usbpd_test", "type": "usb_c_pd"})
    assert mod.type == "usb_c_pd"


def test_sd_card_module_parsing():
    src = Path("libraries/modules/expansion/sd_card.yaml")
    assert src.exists()
    mod = parse_functional_module({"name": "sd_test", "type": "sd_card"})
    assert mod.type == "sd_card"


def test_audio_codec_module_parsing():
    src = Path("libraries/modules/expansion/audio_codec.yaml")
    assert src.exists()
    mod = parse_functional_module({"name": "audio_test", "type": "audio_codec"})
    assert mod.type == "audio_codec"


def test_all_new_modules_in_config(tmp_path):
    """End-to-end: config with all new modules generates without crash."""
    repo_root = Path(__file__).parent.parent
    pcb_src = repo_root / "examples" / "minimal_project" / "main.kicad_pcb"
    sch_src = repo_root / "examples" / "minimal_project" / "main.kicad_sch"

    import shutil
    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_text = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad

functional_modules:
  - name: wifi
    type: wifi_interface
    required: false
  - name: lora
    type: lora_interface
    required: false
  - name: gnss
    type: gnss_module
    required: false
  - name: motor
    type: motor_driver
    required: false
  - name: usbpd
    type: usb_c_pd
    required: false
  - name: sdcard
    type: sd_card
    required: false
  - name: audio
    type: audio_codec
    required: false

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")

    cfg = load_config(cfg_path)
    assert len(cfg.functional_modules) == 7
    report, _ = run(cfg, tmp_path)

    # Should run without crash and produce module reports
    out_dir = tmp_path / "output"
    assert (out_dir / "module_report.txt").exists()
    module_text = (out_dir / "module_report.txt").read_text(encoding="utf-8")
    assert "wifi" in module_text
    assert "lora" in module_text
    assert "gnss" in module_text
    assert "motor" in module_text
    assert "usbpd" in module_text
    assert "sdcard" in module_text
    assert "audio" in module_text
