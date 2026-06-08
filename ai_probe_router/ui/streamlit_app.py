"""Streamlit Web UI for ai-probe-router.

Run with: streamlit run ai_probe_router/ui/streamlit_app.py

Requires: streamlit, matplotlib, pyyaml
"""

from __future__ import annotations

import tempfile
from pathlib import Path

try:
    import streamlit as st
except ImportError:
    raise ImportError("streamlit is required. Install with: pip install streamlit")

from ai_probe_router.config import load_config
from ai_probe_router.engine import run


def _render_pcb_preview(pcb_path: Path):
    """Generate a matplotlib figure from a KiCad PCB file."""
    import re

    import matplotlib.patches as patches
    import matplotlib.pyplot as plt

    text = pcb_path.read_text(encoding="utf-8")
    m = re.search(
        r'\(gr_rect\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+\(end\s+([\d.]+)\s+([\d.]+)\)',
        text,
        re.DOTALL,
    )
    board_rect = (
        (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
        if m else (0, 0, 40, 40)
    )

    fps = []
    for fp in re.finditer(
        r'\(footprint\s+"([^"]+)"\s+(.*?)\n\s*\)', text, re.DOTALL
    ):
        body = fp.group(2)
        at_m = re.search(r'\(at\s+([\d.]+)\s+([\d.]+)', body)
        ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', body)
        if at_m:
            fps.append(
                {
                    "name": fp.group(1),
                    "ref": ref_m.group(1) if ref_m else "?",
                    "x": float(at_m.group(1)),
                    "y": float(at_m.group(2)),
                }
            )

    fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
    bx, by, bxx, byy = board_rect
    w, h = bxx - bx, byy - by
    ax.add_patch(
        patches.Rectangle((bx, by), w, h, linewidth=2, edgecolor="black", facecolor="#e8e8e8")
    )

    for fp in fps:
        if "TestPoint" in fp["name"]:
            ax.add_patch(plt.Circle((fp["x"], fp["y"]), 0.6, color="limegreen", ec="darkgreen"))
            ax.text(fp["x"] + 0.8, fp["y"], fp["ref"], fontsize=5, color="darkgreen")
        elif "Resistor" in fp["name"] or "SOT" in fp["name"]:
            ax.add_patch(
                patches.Rectangle(
                    (fp["x"] - 0.8, fp["y"] - 0.4),
                    1.6,
                    0.8,
                    linewidth=1,
                    edgecolor="purple",
                    facecolor="plum",
                )
            )
        elif "Fiducial" in fp["name"]:
            ax.add_patch(plt.Circle((fp["x"], fp["y"]), 0.5, color="gold", ec="darkgoldenrod"))
        elif "MountingHole" in fp["name"]:
            ax.add_patch(
                plt.Circle(
                    (fp["x"], fp["y"]),
                    1.5,
                    color="white",
                    ec="black",
                    linestyle="--",
                )
            )
        else:
            ax.add_patch(
                patches.Rectangle(
                    (fp["x"] - 5, fp["y"] - 7),
                    10,
                    14,
                    linewidth=1.5,
                    edgecolor="navy",
                    facecolor="lightblue",
                    alpha=0.5,
                )
            )
            ax.text(fp["x"], fp["y"], fp["ref"], ha="center", va="center", fontsize=7, color="navy")

    ax.set_xlim(bx - 5, bxx + 5)
    ax.set_ylim(by - 5, byy + 5)
    ax.set_aspect("equal")
    ax.set_title("PCB Layout Preview")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)


def _render_thermal_heatmap(thermal_csv: Path):
    """Render a thermal heatmap from the thermal simulation CSV."""
    import csv

    import matplotlib.pyplot as plt

    rows = []
    with thermal_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append({
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "current": float(row["current_ma"]),
                    "ref": row.get("ref", ""),
                })
            except (ValueError, KeyError):
                continue

    if not rows:
        st.info("No thermal data available.")
        return

    xs = [r["x"] for r in rows]
    ys = [r["y"] for r in rows]
    currents = [r["current"] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    sc = ax.scatter(xs, ys, c=currents, cmap="hot", s=200, edgecolors="black", alpha=0.8)
    plt.colorbar(sc, ax=ax, label="Current (mA)")
    ax.set_aspect("equal")
    ax.set_title("Thermal Load Map (Current Density)")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)


def main():
    st.set_page_config(page_title="AI Probe Router", layout="wide")
    st.title("AI Probe Router — Interactive Design")

    col_left, col_mid, col_right = st.columns([1, 2, 1])

    with col_left:
        st.header("Configuration")
        yaml_text = st.text_area(
            "Project YAML",
            value=Path("examples/iot_sensor_node_advanced_config.yaml").read_text(
                encoding="utf-8"
            ),
            height=500,
        )

        if st.button("Generate"):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                cfg_path = tmp_path / "config.yaml"
                cfg_path.write_text(yaml_text, encoding="utf-8")
                shutil_src = Path("examples/iot_sensor_node_project")
                for f in ["main.kicad_pcb", "main.kicad_sch"]:
                    src = shutil_src / f
                    if src.exists():
                        import shutil

                        shutil.copy(src, tmp_path / f)
                try:
                    cfg = load_config(cfg_path)
                    report, pin_report = run(cfg, tmp_path)
                    st.session_state["report"] = report
                    st.session_state["pin_report"] = pin_report
                    st.session_state["out_dir"] = tmp_path / "output"
                    st.success("Generation complete!")
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")

    with col_mid:
        st.header("PCB Preview")
        if "out_dir" in st.session_state:
            out_dir = st.session_state["out_dir"]
            pcb_file = out_dir / "main.kicad_pcb"
            thermal_csv = out_dir / "thermal_simulation.csv"
            skew_file = out_dir / "diff_pair_skew_report.txt"

            tab1, tab2 = st.tabs(["Layout", "Thermal"])
            with tab1:
                if pcb_file.exists():
                    _render_pcb_preview(pcb_file)
                else:
                    st.info("No PCB output yet.")
            with tab2:
                if thermal_csv.exists():
                    _render_thermal_heatmap(thermal_csv)
                else:
                    st.info("No thermal data available.")

            if skew_file.exists():
                with st.expander("Diff Pair Skew"):
                    st.text(skew_file.read_text(encoding="utf-8"))
        else:
            st.info("No PCB output yet. Click Generate.")

    with col_right:
        st.header("Reports")
        if "report" in st.session_state:
            r = st.session_state["report"]
            st.metric("Coverage", f"{r.coverage_pct:.0f}%", f"{r.covered}/{r.total_nets_requested}")
            st.metric("DRC", "PASS" if r.drc_ok else "FAIL")
            st.metric("ERC", "PASS" if r.erc_ok else "FAIL")
            st.metric("Constraints", "PASS" if r.constraint_ok else "WARN")
            if r.notes:
                with st.expander("Notes"):
                    for note in r.notes:
                        st.write(f"- {note}")
        else:
            st.info("Run generation to see reports.")


if __name__ == "__main__":
    main()
