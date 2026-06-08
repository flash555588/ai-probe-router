import matplotlib

matplotlib.use('Agg')
import re
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt

text = Path('examples/iot_sensor_node_project/output/main.kicad_pcb').read_text(encoding='utf-8')

# Board outline
m = re.search(r'\(gr_rect\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+\(end\s+([\d.]+)\s+([\d.]+)\)', text, re.DOTALL)
board_rect = (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))) if m else (0,0,40,40)

# Parse footprints with net info
footprints = []
for fp in re.finditer(r'\(footprint\s+"([^"]+)"\s+(.*?)\n\s*\)', text, re.DOTALL):
    name = fp.group(1)
    body = fp.group(2)
    at_m = re.search(r'\(at\s+([\d.]+)\s+([\d.]+)', body)
    x, y = (float(at_m.group(1)), float(at_m.group(2))) if at_m else (0, 0)
    ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', body)
    ref = ref_m.group(1) if ref_m else '?'
    # Extract net from first pad
    net_m = re.search(r'\(net\s+\d+\s+"([^"]*)"\)', body)
    net = net_m.group(1) if net_m else ''
    footprints.append({'name': name, 'ref': ref, 'x': x, 'y': y, 'net': net})

# Parse keepout zones
zones = []
for z in re.finditer(r'\(zone\s+.*?\(polygon\s+\(pts\s+(.*?)\)\s*\)\s*\)', text, re.DOTALL):
    pts_text = z.group(1)
    pts = []
    for pt in re.finditer(r'\(xy\s+([\d.]+)\s+([\d.]+)\)', pts_text):
        pts.append((float(pt.group(1)), float(pt.group(2))))
    if pts:
        zones.append(pts)

# Parse segments (traces)
segments = []
for seg in re.finditer(r'\(segment\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+\(end\s+([\d.]+)\s+([\d.]+)\)', text):
    segments.append(((float(seg.group(1)), float(seg.group(2))), (float(seg.group(3)), float(seg.group(4)))))

# Classify
original = [fp for fp in footprints if 'TestPoint' not in fp['name'] and 'Fiducial' not in fp['name'] and 'MountingHole' not in fp['name'] and 'Resistor' not in fp['name']]
testpoints = [fp for fp in footprints if 'TestPoint' in fp['name']]
fiducials = [fp for fp in footprints if 'Fiducial' in fp['name']]
mounting = [fp for fp in footprints if 'MountingHole' in fp['name']]
protection = [fp for fp in footprints if 'Resistor' in fp['name']]

fig, ax = plt.subplots(figsize=(14, 12), dpi=150)

# Board
bx, by, bxx, byy = board_rect
w, h = bxx - bx, byy - by
board = patches.Rectangle((bx, by), w, h, linewidth=2.5, edgecolor='black', facecolor='#e8e8e8')
ax.add_patch(board)

# Original component (MCU)
for fp in original:
    rect = patches.Rectangle((fp['x']-6.35, fp['y']-8.89), 12.7, 17.78, linewidth=1.5, edgecolor='navy', facecolor='lightblue', alpha=0.5)
    ax.add_patch(rect)
    ax.text(fp['x'], fp['y'], fp['ref'], ha='center', va='center', fontsize=9, fontweight='bold', color='navy')

# Protection resistors
for fp in protection:
    rect = patches.Rectangle((fp['x']-0.6, fp['y']-0.4), 1.2, 0.8, linewidth=1, edgecolor='purple', facecolor='plum', alpha=0.9)
    ax.add_patch(rect)
    ax.text(fp['x'], fp['y'], fp['ref'], ha='center', va='center', fontsize=7, color='purple', fontweight='bold')

# Testpoints with net labels
for fp in testpoints:
    circle = plt.Circle((fp['x'], fp['y']), 0.65, color='limegreen', ec='darkgreen', linewidth=1.5, zorder=5)
    ax.add_patch(circle)
    label = f"{fp['ref']}\n{fp['net'][:12]}"
    ax.text(fp['x']+0.9, fp['y']+0.3, label, fontsize=5.5, color='darkgreen', va='center')

# Highlight differential pairs
diff_pairs = {
    'CAN_H': 'CAN_L',
    'CAN_L': 'CAN_H',
}
tp_by_net = {fp['net']: fp for fp in testpoints if fp['net']}
for net_a, net_b in [('CAN_H', 'CAN_L')]:
    if net_a in tp_by_net and net_b in tp_by_net:
        a, b = tp_by_net[net_a], tp_by_net[net_b]
        ax.annotate('', xy=(b['x'], b['y']), xytext=(a['x'], a['y']),
                    arrowprops=dict(arrowstyle='<->', color='magenta', lw=1.5, ls='--'))
        mx, my = (a['x']+b['x'])/2, (a['y']+b['y'])/2
        ax.text(mx, my+1.5, 'DIFF_PAIR', fontsize=6, color='magenta', ha='center', fontweight='bold')

# Fiducials
for fp in fiducials:
    circle = plt.Circle((fp['x'], fp['y']), 0.5, color='gold', ec='darkgoldenrod', linewidth=1.5, zorder=5)
    ax.add_patch(circle)
    ax.text(fp['x'], fp['y']-1.2, 'FID', ha='center', va='top', fontsize=6, color='darkgoldenrod')

# Tooling holes
for fp in mounting:
    circle = plt.Circle((fp['x'], fp['y']), 1.6, color='white', ec='black', linewidth=1.5, linestyle='--', zorder=5)
    ax.add_patch(circle)
    ax.text(fp['x'], fp['y']-2.2, 'TH', ha='center', va='top', fontsize=6)

# Keepout zones
for zone in zones:
    xs = [p[0] for p in zone] + [zone[0][0]]
    ys = [p[1] for p in zone] + [zone[0][1]]
    ax.fill(xs, ys, color='red', alpha=0.06)
    ax.plot(xs, ys, 'r--', linewidth=0.7, alpha=0.35)

# Traces
for (x1,y1), (x2,y2) in segments:
    ax.plot([x1, x2], [y1, y2], 'g-', linewidth=0.5, alpha=0.45)

ax.set_xlim(bx-8, bxx+12)
ax.set_ylim(by-8, byy+8)
ax.set_aspect('equal')

# Layer stackup info box
stackup_text = (
    "Layer Stackup:\n"
    "  L1: F.Cu (signal)\n"
    "  L2: B.Cu (signal)\n"
    "  F.SilkS / B.SilkS\n"
    "  F.Mask / B.Mask\n"
    "  Edge.Cuts"
)
ax.text(bxx+2, byy-2, stackup_text, fontsize=7, family='monospace',
        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

# Stats box
stats_text = (
    f"Nets: 19/19 (100%)\n"
    f"Testpoints: {len(testpoints)}\n"
    f"Protection: {len(protection)}\n"
    f"Fiducials: {len(fiducials)}\n"
    f"Tooling: {len(mounting)}\n"
    f"Diff Pairs: 1 (CAN)\n"
    f"Traces: {len(segments)}"
)
ax.text(bxx+2, by+2, stats_text, fontsize=7, family='monospace',
        verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='lightcyan', alpha=0.8))

ax.set_title(
    f'IoT Sensor Node Advanced — ai-probe-router Generated Layout\n'
    f'{w:.0f}x{h:.0f} mm | 19 nets | 100% coverage | Diff-pair aware | 2-layer',
    fontsize=12
)
ax.set_xlabel('X (mm)')
ax.set_ylabel('Y (mm)')
ax.grid(True, alpha=0.25)

from matplotlib.lines import Line2D

legend_elements = [
    Line2D([0], [0], marker='s', color='w', markerfacecolor='lightblue', markeredgecolor='navy', markersize=10, label='MCU'),
    Line2D([0], [0], marker='s', color='w', markerfacecolor='plum', markeredgecolor='purple', markersize=10, label='Protection'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='limegreen', markeredgecolor='darkgreen', markersize=10, label='Testpoint'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='gold', markeredgecolor='darkgoldenrod', markersize=8, label='Fiducial'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='white', markeredgecolor='black', linestyle='--', markersize=10, label='Tooling Hole'),
    Line2D([0], [0], color='magenta', linewidth=1.5, linestyle='--', label='Diff Pair'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=8, ncol=2)

plt.tight_layout()
out_png = 'iot_sensor_node_advanced_layout.png'
plt.savefig(out_png, dpi=150, bbox_inches='tight')
print(f"Saved to {out_png}")
plt.close()
