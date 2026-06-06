"""CLI entry point for ai-probe-router."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import load_config
from .engine import run

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
    table.add_column("Location")
    for e in report.entries:
        tp = "[green]YES[/]" if e.has_testpoint else "[red]NO[/]"
        req = "YES" if e.required else "no"
        loc = f"({e.probe_x:.1f}, {e.probe_y:.1f}) {e.side}" if e.has_testpoint else "—"
        table.add_row(e.net_name, e.role.name, req, tp, loc)
    console.print(table)
    console.print()
    console.print(f"Coverage: {report.coverage_pct:.0f}% "
                  f"({report.covered}/{report.total_nets_requested})")
    if report.drc_ok is not None:
        s = "[green]PASS[/]" if report.drc_ok else f"[red]FAIL ({report.drc_violations})[/]"
        console.print(f"DRC: {s}")
    if report.erc_ok is not None:
        s = "[green]PASS[/]" if report.erc_ok else f"[red]FAIL ({report.erc_violations})[/]"
        console.print(f"ERC: {s}")
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


if __name__ == "__main__":
    main()
