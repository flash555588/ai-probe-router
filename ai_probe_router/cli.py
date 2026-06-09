"""CLI entry point for ai-probe-router."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import load_config
from .eda_adapters.kicad.pcb_parser import parse_pcb
from .eda_adapters.kicad.pcb_writer import write_pcb
from .engine import run
from .routing.ses_import import import_ses

console = Console()


@click.group()
@click.version_option(package_name="ai-probe-router")
def main():
    """AI-assisted KiCad probe/test interface designer."""


@main.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--project-dir", "-d", type=click.Path(exists=True), default=".",
              help="KiCad project directory")
def generate(config_file: str, project_dir: str):
    """Generate testpoints from a YAML config."""
    cfg = load_config(config_file)
    console.print(f"[bold]Loading config:[/] {config_file}")
    console.print(f"[bold]Project dir:[/]   {project_dir}")
    console.print(f"[bold]Schematic:[/]     {cfg.schematic_file}")
    console.print(f"[bold]PCB:[/]           {cfg.board_file}")
    console.print(f"[bold]Nets to expose:[/] {len(cfg.nets_to_expose)}")
    console.print()

    report, pin_report = run(cfg, project_dir)

    if pin_report is not None and pin_report.result.assignments:
        ptable = Table(title="Pin Mapping")
        ptable.add_column("Net", style="cyan")
        ptable.add_column("Pin", style="green")
        ptable.add_column("Score", justify="right")
        for a in pin_report.result.assignments:
            ptable.add_row(a.net_name, a.pin_name, f"{a.score:.1f}")
        console.print(ptable)
        console.print()
        if pin_report.result.errors:
            console.print("[red]Mapping errors:[/]")
            for e in pin_report.result.errors:
                console.print(f"  - {e}")
            console.print()

    table = Table(title="Testpoint Coverage")
    table.add_column("Net", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("Required")
    table.add_column("Testpoint")
    table.add_column("Review")
    table.add_column("Trace", justify="right")
    table.add_column("Clr", justify="right")
    table.add_column("Location")
    for e in report.entries:
        tp = "[green]YES[/]" if e.has_testpoint else "[red]NO[/]"
        req = "YES" if e.required else "no"
        rev = "[yellow]YES[/]" if e.review_required else "no"
        loc = f"({e.probe_x:.1f}, {e.probe_y:.1f}) {e.side}" if e.has_testpoint else "—"
        table.add_row(
            e.net_name, e.role.name, req, tp, rev,
            f"{e.trace_width_mm:.2f}", f"{e.clearance_mm:.2f}", loc,
        )
    console.print(table)
    console.print()
    console.print(f"Coverage: {report.coverage_pct:.0f}% "
                  f"({report.covered}/{report.total_nets_requested})")
    if report.drc_ok is not None:
        if report.drc_ok:
            s = "[green]PASS[/]"
        else:
            s = f"[red]FAIL ({report.drc_violations})[/]"
        console.print(f"DRC: {s}")
    else:
        console.print("DRC: [dim]SKIPPED (kicad-cli not found)[/]")
    if report.erc_ok is not None:
        if report.erc_ok:
            s = "[green]PASS[/]"
        else:
            s = f"[red]FAIL ({report.erc_violations})[/]"
        console.print(f"ERC: {s}")
    else:
        console.print("ERC: [dim]SKIPPED (kicad-cli not found)[/]")
    if report.constraint_ok is not None:
        if report.constraint_ok:
            s = "[green]PASS[/]"
        else:
            s = f"[yellow]WARN ({report.constraint_violations})[/]"
        console.print(f"Constraints: {s}")
        for msg in report.constraint_messages:
            console.print(f"  [dim]- {msg}[/]")
    console.print(f"\nOutput written to: {Path(project_dir) / 'output'}")


@main.command()
@click.argument("pcb_file", type=click.Path(exists=True))
def inspect(pcb_file: str):
    """Inspect a KiCad PCB and list nets."""
    from .ai.net_classifier import classify_net
    from .eda_adapters.kicad.pcb_parser import parse_pcb

    board = parse_pcb(pcb_file)
    table = Table(title=f"Nets in {Path(pcb_file).name}")
    table.add_column("ID", justify="right")
    table.add_column("Net Name", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("Pads", justify="right")
    for name, net_id in sorted(board.nets.items(), key=lambda x: x[1]):
        if not name:
            continue
        role = classify_net(name)
        pad_count = sum(1 for fp in board.footprints for p in fp.pads if p.net_name == name)
        table.add_row(str(net_id), name, role.name, str(pad_count))
    console.print(table)
    console.print(f"\nTotal nets: {len(board.nets) - 1}")
    console.print(f"Footprints: {len(board.footprints)}")
    bounds = board.board_bounds()
    if bounds:
        console.print(f"Board size: {bounds.width:.1f} x {bounds.height:.1f} mm")


@main.command()
@click.argument("sch_file", type=click.Path(exists=True))
def inspect_sch(sch_file: str):
    """Inspect a KiCad schematic and list components."""
    from .eda_adapters.kicad.sch_parser import parse_schematic

    sch = parse_schematic(sch_file)
    table = Table(title=f"Components in {Path(sch_file).name}")
    table.add_column("Ref", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Lib", style="dim")
    table.add_column("Position")
    for comp in sch.components:
        table.add_row(comp.ref, comp.value, comp.lib_id,
                      f"({comp.x:.1f}, {comp.y:.1f})")
    console.print(table)
    console.print(f"\nComponents: {len(sch.components)}")
    console.print(f"Net labels: {len(sch.labels)}")
    console.print(f"Wires: {len(sch.wires)}")


@main.command()
@click.argument("pcb_file", type=click.Path(exists=True))
@click.argument("ses_file", type=click.Path(exists=True))
def route(pcb_file: str, ses_file: str):
    """Import FreeRouting SES result into a KiCad PCB."""
    board = parse_pcb(pcb_file)
    import_ses(board, ses_file)
    out_path = Path(pcb_file).with_suffix(".routed.kicad_pcb")
    write_pcb(board, out_path)
    console.print(f"[green]Routed PCB written to:[/] {out_path}")
    segs = sum(1 for n in board.raw if isinstance(n, list) and n[0] == "segment")
    vias = sum(1 for n in board.raw if isinstance(n, list) and n[0] == "via")
    console.print(f"Segments: {segs}, Vias: {vias}")


@main.command()
@click.argument("pcb_file", type=click.Path(exists=True))
def validate(pcb_file: str):
    """Validate probe placement on an existing PCB."""
    from .eda_adapters.kicad.pcb_parser import parse_pcb
    from .models.constraints import Constraints
    from .models.probe import ProbeConfig
    from .solvers.constraint_checker import validate_all_probes

    board = parse_pcb(pcb_file)
    testpoints = []
    for fp in board.footprints:
        if fp.ref.startswith("TP"):
            net = fp.pads[0].net_name if fp.pads else ""
            testpoints.append((fp.x, fp.y, net))
    if not testpoints:
        console.print("[yellow]No testpoints found in PCB.[/]")
        return
    result = validate_all_probes(testpoints, board, Constraints(), ProbeConfig())
    if result.ok:
        console.print(f"[green]All {len(testpoints)} testpoints pass constraint checks.[/]")
    else:
        console.print(f"[red]{len(result.violations)} constraint violations found:[/]")
        for v in result.violations:
            style = "red" if v.severity == "error" else "yellow"
            console.print(f"  [{style}]{v.rule}[/]: {v.message}")


@main.command()
@click.argument("sch_file", type=click.Path(exists=True))
@click.option("--pcb", type=click.Path(exists=True), default=None,
              help="Optional PCB file for spatial analysis")
@click.option("--mcu", type=str, default=None,
              help="MCU profile name (e.g., esp32-s3) or path to YAML")
def review(sch_file: str, pcb: str | None, mcu: str | None):
    """Run design review checks on a schematic."""
    from .ai.design_review import run_design_review
    from .eda_adapters.kicad.sch_parser import parse_schematic
    from .models.mcu_profile import McuProfile, load_mcu_profile

    sch = parse_schematic(sch_file)
    board = None
    if pcb:
        board = parse_pcb(pcb)

    mcu_profile: McuProfile | None = None
    if mcu:
        mcu_path = Path(mcu)
        if mcu_path.exists():
            mcu_profile = load_mcu_profile(mcu_path)
        else:
            builtin = (
                Path(__file__).parent.parent
                / "libraries"
                / "mcu_profiles"
                / f"{mcu.replace('-', '_')}.yaml"
            )
            if builtin.exists():
                mcu_profile = load_mcu_profile(builtin)
            else:
                console.print(f"[red]MCU profile not found:[/] {mcu}")
                return

    report = run_design_review(sch, board, mcu_profile)

    if not report.findings:
        console.print("[green]No design issues found.[/]")
        return

    table = Table(title="Design Review Findings")
    table.add_column("Severity", style="bold")
    table.add_column("ID")
    table.add_column("Category", style="cyan")
    table.add_column("Component", style="green")
    table.add_column("Message")
    table.add_column("Suggestion", style="dim")

    for f in report.findings:
        sev_style = {"error": "red", "warning": "yellow", "info": "blue"}.get(f.severity, "white")
        table.add_row(
            f"[{sev_style}]{f.severity.upper()}[/{sev_style}]",
            f.check_id, f.category, f.component_ref,
            f.message, f.suggestion,
        )

    console.print(table)
    console.print()
    console.print(
        f"Summary: [red]{report.error_count} errors[/], "
        f"[yellow]{report.warning_count} warnings[/], "
        f"{len(report.findings) - report.error_count - report.warning_count} info"
    )


@main.command()
@click.argument("output_dir", type=click.Path(exists=True), default="output")
@click.option("--step", type=click.Path(exists=False), default=None,
              help="Optional STEP file for 3D board view")
@click.option("--no-3d", is_flag=True, default=False,
              help="Disable 3D view (tables only)")
def plugin_shell(output_dir: str, step: str | None, no_3d: bool):
    """Launch the KiCad plugin shell GUI."""
    from pathlib import Path

    try:
        from ai_probe_router.ui.plugin_shell import KiCadPluginShell

        step_path = Path(step) if step else None
        shell = KiCadPluginShell(
            Path(output_dir),
            step_path=step_path,
            enable_3d=not no_3d,
        )
        shell.load_reports()
        return shell.run()
    except ImportError as exc:
        raise click.ClickException(
            f'{exc}. Install with: uv pip install -e ".[plugin]"'
        ) from exc


if __name__ == "__main__":
    main()
