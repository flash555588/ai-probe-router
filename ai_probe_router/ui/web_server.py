"""FastAPI web server for AI Probe Router.

Provides a browser-based UI to upload KiCad projects, edit configuration,
and download generated outputs.

Usage::

    uvicorn ai_probe_router.ui.web_server:app --reload --port 8000

Or programmatically::

    from ai_probe_router.ui.web_server import run_server
    run_server(host="127.0.0.1", port=8000)
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from ..config import load_config
from ..engine import run as engine_run

app = FastAPI(title="AI Probe Router")

# Locate templates relative to this file
_TEMPLATES = Path(__file__).with_suffix("").parent / "templates"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the main upload page."""
    html_path = _TEMPLATES / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="index.html not found")
    return html_path.read_text(encoding="utf-8")


@app.post("/generate")
def generate(
    pcb: Annotated[UploadFile, File()],
    config: Annotated[UploadFile, File()],
    sch: Annotated[UploadFile | None, File()] = None,
) -> dict:
    """Accept uploaded files, run the engine, and return result metadata."""
    # Validate PCB extension
    if not pcb.filename or not pcb.filename.lower().endswith(".kicad_pcb"):
        raise HTTPException(status_code=400, detail="pcb must be a .kicad_pcb file")

    with tempfile.TemporaryDirectory(prefix="apr_web_") as tmp:
        tmp_path = Path(tmp)

        # Save PCB
        pcb_path = tmp_path / Path(pcb.filename).name
        pcb_path.write_bytes(pcb.file.read())

        # Save schematic if provided
        if sch and sch.filename:
            sch_path = tmp_path / Path(sch.filename).name
            sch_path.write_bytes(sch.file.read())

        # Save config
        if not config.filename:
            raise HTTPException(status_code=400, detail="config file required")
        cfg_path = tmp_path / Path(config.filename).name
        cfg_path.write_bytes(config.file.read())

        # Load config
        try:
            cfg = load_config(cfg_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid config: {exc}") from exc

        # Run engine
        try:
            coverage, _pin_report = engine_run(cfg, tmp_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Engine error: {exc}") from exc

        out_dir = tmp_path / "output"
        if not out_dir.exists():
            raise HTTPException(status_code=500, detail="No output generated")

        # Gather result files as base64
        files = []
        for f in sorted(out_dir.iterdir()):
            if f.is_file():
                data = f.read_bytes()
                files.append({
                    "name": f.name,
                    "size": _human_size(len(data)),
                    "content": base64.b64encode(data).decode("ascii"),
                })

        return {
            "ok": True,
            "files": files,
            "report": coverage.summary_text(),
            "coverage_pct": coverage.coverage_pct,
            "drc_ok": coverage.drc_ok,
            "erc_ok": coverage.erc_ok,
        }


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the development server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
