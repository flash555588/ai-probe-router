"""Coordinate transformations between KiCad PCB and 3D STEP space.

Maps footprint (x, y) coordinates in mm to the 3D view frame, including
layer height offsets for top vs bottom placements.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardCoordinateFrame:
    """Defines the mapping from PCB mm to 3D world units."""

    origin_x: float = 0.0
    origin_y: float = 0.0
    scale: float = 1.0          # mm → world units
    top_z: float = 1.0          # z height for top-layer footprints
    bottom_z: float = -1.0      # z height for bottom-layer footprints
    board_thickness_mm: float = 1.6

    def pcb_to_world(
        self,
        x_mm: float,
        y_mm: float,
        side: str = "top",
    ) -> tuple[float, float, float]:
        """Map a PCB (x, y) coordinate to 3D world space."""
        wx = (x_mm - self.origin_x) * self.scale
        wy = (y_mm - self.origin_y) * self.scale
        wz = self.top_z if side.lower() == "top" else self.bottom_z
        return (wx, wy, wz)

    def world_to_pcb(self, wx: float, wy: float) -> tuple[float, float]:
        """Inverse map from world space back to PCB mm."""
        x_mm = wx / self.scale + self.origin_x
        y_mm = wy / self.scale + self.origin_y
        return (x_mm, y_mm)


def fit_frame_to_board(
    board_width_mm: float,
    board_height_mm: float,
    target_viewport_size: float = 100.0,
    board_thickness_mm: float = 1.6,
) -> BoardCoordinateFrame:
    """Create a coordinate frame that fits the board into a target viewport.

    The board is centered at the origin and scaled so its larger dimension
    matches *target_viewport_size*.
    """
    max_dim = max(board_width_mm, board_height_mm)
    scale = target_viewport_size / max_dim if max_dim > 0 else 1.0
    return BoardCoordinateFrame(
        origin_x=board_width_mm / 2.0,
        origin_y=board_height_mm / 2.0,
        scale=scale,
        top_z=board_thickness_mm / 2.0 + 0.5,
        bottom_z=-(board_thickness_mm / 2.0 + 0.5),
        board_thickness_mm=board_thickness_mm,
    )
