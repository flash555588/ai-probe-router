"""KiCad Plugin Shell — PyQt6 GUI for ai-probe-router reports.

Displays footprint preview, resource allocation, route import status,
and a 3D VTK view.  All heavy dependencies are imported lazily so the
module can be parsed without PyQt6 or vtk installed.

Run standalone:
    python -m ai_probe_router.ui.plugin_shell <output_dir>
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6 import QtWidgets
    from PyQt6.QtWidgets import QWidget


def _require_pyqt6():
    try:
        from PyQt6 import QtWidgets
        return QtWidgets
    except ImportError as exc:
        raise ImportError(
            "PyQt6 is required for the plugin shell. "
            "Install with: pip install PyQt6"
        ) from exc


def _require_vtk_qt():
    try:
        from vtkmodules.qt.QVTKRenderWindowInteractor import (
            QVTKRenderWindowInteractor,
        )
        return QVTKRenderWindowInteractor
    except ImportError as exc:
        raise ImportError(
            "vtk with Qt support is required for the 3D view. "
            "Install with: pip install vtk"
        ) from exc


class KiCadPluginShell:
    """Main plugin window.

    This class is defined without inheriting from QMainWindow at import
    time so that test collection never fails when PyQt6 is absent.
    The real window is created on ``run()``.
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.footprint_data = None
        self.resource_data = None
        self.readiness_data = None
        self._window: "QtWidgets.QMainWindow | None" = None

    # ------------------------------------------------------------------ #
    #  Report loading
    # ------------------------------------------------------------------ #
    def load_reports(self) -> None:
        from .report_loader import (
            load_footprint_preview,
            load_readiness,
            load_resource_allocation,
        )

        self.footprint_data = load_footprint_preview(
            self.output_dir / "footprint_preview_report.json"
        )
        self.resource_data = load_resource_allocation(
            self.output_dir / "resource_allocation_report.json"
        )
        self.readiness_data = load_readiness(
            self.output_dir / "readiness_report.json"
        )

    # ------------------------------------------------------------------ #
    #  GUI construction
    # ------------------------------------------------------------------ #
    def run(self) -> int:
        """Build the GUI and start the Qt event loop."""
        QtWidgets = _require_pyqt6()
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])

        self._window = QtWidgets.QMainWindow()
        self._window.setWindowTitle("AI Probe Router — KiCad Plugin Shell")
        self._window.resize(1200, 800)

        self._build_menu()
        self._build_tabs()
        self._build_status_bar()

        self._window.show()
        return app.exec()

    def _build_menu(self) -> None:
        _require_pyqt6()
        menu = self._window.menuBar()
        file_menu = menu.addMenu("File")

        open_action = file_menu.addAction("Open Output Folder…")
        open_action.triggered.connect(self._on_open_folder)

        refresh_action = file_menu.addAction("Refresh Reports")
        refresh_action.triggered.connect(self._on_refresh)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self._window.close)

    def _build_tabs(self) -> None:
        QtWidgets = _require_pyqt6()
        tabs = QtWidgets.QTabWidget()
        self._window.setCentralWidget(tabs)

        tabs.addTab(self._build_footprint_tab(), "Footprint Preview")
        tabs.addTab(self._build_resource_tab(), "Resource Allocation")
        tabs.addTab(self._build_route_tab(), "Route Import")
        tabs.addTab(self._build_3d_tab(), "3D View")

    def _build_status_bar(self) -> None:
        QtWidgets = _require_pyqt6()
        status = QtWidgets.QLabel("Ready")
        self._window.statusBar().addWidget(status)
        self._status_label = status
        self._update_status()

    def _update_status(self) -> None:
        if self.readiness_data is None:
            self._status_label.setText("No reports loaded")
            return
        r = self.readiness_data
        color = "green"
        if r.verdict == "BLOCKED":
            color = "red"
        elif r.verdict == "PASS_WITH_REVIEW":
            color = "orange"
        self._status_label.setText(
            f"Verdict: {r.verdict} | Blockers: {len(r.blockers)} | "
            f"Warnings: {len(r.warnings)}"
        )
        self._status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    # ------------------------------------------------------------------ #
    #  Tab builders
    # ------------------------------------------------------------------ #
    def _build_footprint_tab(self) -> "QWidget":
        QtWidgets = _require_pyqt6()
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Issues list
        issues_group = QtWidgets.QGroupBox("Issues")
        issues_layout = QtWidgets.QVBoxLayout()
        self._footprint_issues_list = QtWidgets.QListWidget()
        issues_layout.addWidget(self._footprint_issues_list)
        issues_group.setLayout(issues_layout)
        layout.addWidget(issues_group, stretch=1)

        # Footprints table
        table = QtWidgets.QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(
            ["Reference", "Module", "Footprint", "X", "Y", "Side", "Role"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        self._footprint_table = table
        layout.addWidget(table, stretch=2)

        widget.setLayout(layout)
        self._refresh_footprint_tab()
        return widget

    def _build_resource_tab(self) -> "QWidget":
        QtWidgets = _require_pyqt6()
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Buses
        bus_group = QtWidgets.QGroupBox("Bus Assignments")
        bus_table = QtWidgets.QTableWidget()
        bus_table.setColumnCount(4)
        bus_table.setHorizontalHeaderLabels(["Bus", "Module", "Instance", "Address"])
        bus_table.horizontalHeader().setStretchLastSection(True)
        self._bus_table = bus_table
        bus_layout = QtWidgets.QVBoxLayout()
        bus_layout.addWidget(bus_table)
        bus_group.setLayout(bus_layout)
        layout.addWidget(bus_group, stretch=1)

        # Power
        power_group = QtWidgets.QGroupBox("Power Domains")
        power_table = QtWidgets.QTableWidget()
        power_table.setColumnCount(5)
        power_table.setHorizontalHeaderLabels(
            ["Domain", "Voltage", "Budget mA", "Requested mA", "Headroom %"]
        )
        power_table.horizontalHeader().setStretchLastSection(True)
        self._power_table = power_table
        power_layout = QtWidgets.QVBoxLayout()
        power_layout.addWidget(power_table)
        power_group.setLayout(power_layout)
        layout.addWidget(power_group, stretch=1)

        widget.setLayout(layout)
        self._refresh_resource_tab()
        return widget

    def _build_route_tab(self) -> "QWidget":
        QtWidgets = _require_pyqt6()
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        blockers_group = QtWidgets.QGroupBox("Blockers")
        self._blockers_list = QtWidgets.QListWidget()
        blockers_layout = QtWidgets.QVBoxLayout()
        blockers_layout.addWidget(self._blockers_list)
        blockers_group.setLayout(blockers_layout)
        layout.addWidget(blockers_group, stretch=1)

        warnings_group = QtWidgets.QGroupBox("Warnings")
        self._warnings_list = QtWidgets.QListWidget()
        warnings_layout = QtWidgets.QVBoxLayout()
        warnings_layout.addWidget(self._warnings_list)
        warnings_group.setLayout(warnings_layout)
        layout.addWidget(warnings_group, stretch=1)

        widget.setLayout(layout)
        self._refresh_route_tab()
        return widget

    def _build_3d_tab(self) -> "QWidget":
        QtWidgets = _require_pyqt6()
        QVTKRenderWindowInteractor = _require_vtk_qt()

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        self._vtk_widget = QVTKRenderWindowInteractor(widget)
        layout.addWidget(self._vtk_widget)

        # Refresh button
        btn = QtWidgets.QPushButton("Refresh 3D View")
        btn.clicked.connect(self._refresh_3d_view)
        layout.addWidget(btn)

        widget.setLayout(layout)
        self._refresh_3d_view()
        return widget

    # ------------------------------------------------------------------ #
    #  Refresh logic
    # ------------------------------------------------------------------ #
    def _refresh_footprint_tab(self) -> None:
        data = self.footprint_data
        if data is None:
            return

        # Issues
        self._footprint_issues_list.clear()
        for issue in data.issues:
            icon = (
                "🔴"
                if issue.severity == "error"
                else "🟡"
                if issue.severity == "warning"
                else "ℹ️"
            )
            self._footprint_issues_list.addItem(
                f"{icon} [{issue.code}] {issue.message}"
            )

        # Table
        self._footprint_table.setRowCount(len(data.footprints))
        for row, fp in enumerate(data.footprints):
            self._footprint_table.setItem(row, 0, self._item(fp.reference))
            self._footprint_table.setItem(row, 1, self._item(fp.module_name))
            self._footprint_table.setItem(row, 2, self._item(fp.footprint))
            self._footprint_table.setItem(row, 3, self._item(f"{fp.x_mm:.2f}"))
            self._footprint_table.setItem(row, 4, self._item(f"{fp.y_mm:.2f}"))
            self._footprint_table.setItem(row, 5, self._item(fp.side))
            self._footprint_table.setItem(row, 6, self._item(fp.role or ""))

    def _refresh_resource_tab(self) -> None:
        data = self.resource_data
        if data is None:
            return

        self._bus_table.setRowCount(len(data.buses))
        for row, bus in enumerate(data.buses):
            self._bus_table.setItem(
                row, 0, self._item(f"{bus.bus_type.upper()}-{bus.bus_id}")
            )
            self._bus_table.setItem(row, 1, self._item(bus.module))
            self._bus_table.setItem(row, 2, self._item(bus.instance_id))
            self._bus_table.setItem(row, 3, self._item(bus.address))

        self._power_table.setRowCount(len(data.power))
        for row, domain in enumerate(data.power):
            self._power_table.setItem(row, 0, self._item(domain.domain))
            self._power_table.setItem(
                row, 1, self._item(f"{domain.voltage}V")
            )
            self._power_table.setItem(
                row, 2, self._item(f"{domain.budget_ma:.1f}")
            )
            self._power_table.setItem(
                row, 3, self._item(f"{domain.requested_ma:.1f}")
            )
            self._power_table.setItem(
                row, 4, self._item(f"{domain.headroom_percent:.1f}")
            )

    def _refresh_route_tab(self) -> None:
        data = self.readiness_data
        if data is None:
            return

        self._blockers_list.clear()
        for b in data.blockers:
            self._blockers_list.addItem(f"[{b.source}] {b.message}")

        self._warnings_list.clear()
        for w in data.warnings:
            self._warnings_list.addItem(f"[{w.source}] {w.message}")

    def _refresh_3d_view(self) -> None:
        if self.footprint_data is None:
            return
        from .vtk_3d_view import build_3d_scene

        renderer = build_3d_scene(
            self.footprint_data.footprints,
            self.footprint_data.issues,
        )
        self._vtk_widget.GetRenderWindow().AddRenderer(renderer)
        self._vtk_widget.GetRenderWindow().Render()

    def _item(self, text: str):
        QtWidgets = _require_pyqt6()
        from PyQt6.QtCore import Qt
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    # ------------------------------------------------------------------ #
    #  Actions
    # ------------------------------------------------------------------ #
    def _on_open_folder(self) -> None:
        QtWidgets = _require_pyqt6()
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self._window,
            "Select Output Directory",
            str(self.output_dir),
        )
        if path:
            self.output_dir = Path(path)
            self._on_refresh()

    def _on_refresh(self) -> None:
        self.load_reports()
        self._refresh_footprint_tab()
        self._refresh_resource_tab()
        self._refresh_route_tab()
        self._update_status()
        self._refresh_3d_view()


def main() -> int:
    import sys

    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output")
    shell = KiCadPluginShell(output_dir)
    shell.load_reports()
    return shell.run()


if __name__ == "__main__":
    raise SystemExit(main())
