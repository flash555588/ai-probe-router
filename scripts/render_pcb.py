import re
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt

text = Path('examples/bluetooth_module/output/main.kicad_pcb').read_text(encoding='utf-8')
lines = text.splitlines()
footprints = []
current_fp = None

for line in lines:
    m = re.search(r'\(footprint\s+"([^"]+)"', line)
    if m:
        current_fp = m.group(1)
        continue
    if current_fp:
        m2 = re.search(r'\(at\s+([\d.]+)\s+([\d.]+)', line)
        if m2:
            x, y = float(m2.group(1)), float(m2.group(2))
            footprints.append((current_fp, x, y))
            current_fp = None

keepout_pts = []
zone_match = re.search(
    r'\(zone\s+.*?\(polygon\s+\(pts\s+(.*?)\)\)',
    text, re.DOTALL
)
if zone_match:
    pts_text = zone_match.group(1)
    for m in re.finditer(r'\(xy\s+([\d.]+)\s+([\d.]+)\)', pts_text):
        keepout_pts.append((float(m.group(1)), float(m.group(2))))

fig, ax = plt.subplots(figsize=(10, 8), dpi=120)

board = patches.Rectangle((30, 35), 40, 30, linewidth=2, edgecolor='black', facecolor='#e8e8e8')
ax.add_patch(board)

if keepout_pts:
    kx = [p[0] for p in keepout_pts] + [keepout_pts[0][0]]
    ky = [p[1] for p in keepout_pts] + [keepout_pts[0][1]]
    ax.fill(kx, ky, color='red', alpha=0.15, hatch='///')
    ax.plot(kx, ky, 'r--', linewidth=1, alpha=0.6)

original = []
testpoints = []
fiducials = []
mounting = []
protection = []

for name, x, y in footprints:
    if 'TestPoint' in name:
        testpoints.append((x, y))
    elif 'Fiducial' in name:
        fiducials.append((x, y))
    elif 'MountingHole' in name:
        mounting.append((x, y))
    elif 'Resistor_SMD:R_0603' in name or 'Inductor' in name or 'Ferrite' in name or 'FB' in name:
        protection.append((name, x, y))
    elif 'Resistor_SMD:R_0402' in name and (x, y) == (60.0, 55.0):
        original.append((name, x, y))
    else:
        original.append((name, x, y))

comp_info = {
    'RF_Module:Bluetooth_HC-05': ('U1\nHC-05', 20, 25, 'lightblue'),
    'LED_SMD:LED_0603_1608Metric': ('D1\nLED', 1.6, 0.8, 'yellow'),
    'Connector_PinHeader_1.00mm:PinHeader_1x06_P1.00mm_Vertical': ('J1\nCONN', 6, 1, 'lightgreen'),
    'Capacitor_SMD:C_0402_1005Metric': ('C1\n100n', 1, 0.8, 'orange'),
    'Resistor_SMD:R_0402_1005Metric': ('R1\n1k', 1, 0.5, 'pink'),
}
for name, x, y in original:
    info = comp_info.get(name, ('?', 2, 2, 'gray'))
    label, w, h, color = info
    rect = patches.Rectangle((x - w/2, y - h/2), w, h, linewidth=1, edgecolor='navy', facecolor=color, alpha=0.7)
    ax.add_patch(rect)
    ax.text(x, y, label, ha='center', va='center', fontsize=7, fontweight='bold')

for name, x, y in protection:
    rect = patches.Rectangle((x - 0.8, y - 0.4), 1.6, 0.8, linewidth=1, edgecolor='purple', facecolor='plum', alpha=0.8)
    ax.add_patch(rect)
    ax.text(x, y, 'FB1', ha='center', va='center', fontsize=7, color='purple', fontweight='bold')

tp_labels = [
    (43.18, 60.96, 'TP1\nVCC'),
    (40.64, 55.88, 'TP2\nGND'),
    (45.72, 50.80, 'TP3\nUART_TX'),
    (45.72, 55.88, 'TP4\nGND'),
    (40.64, 50.80, 'TP5\nGND'),
    (48.26, 48.26, 'TP6\nUART_RX'),
    (43.18, 43.18, 'TP7\nSTATE'),
    (66.04, 58.42, 'TP8\nLED'),
    (53.34, 58.42, 'TP9\nEN'),
]
for x, y, label in tp_labels:
    circle = plt.Circle((x, y), 0.65, color='limegreen', ec='darkgreen', linewidth=1.5, zorder=5)
    ax.add_patch(circle)
    ax.text(x + 1.5, y, label, fontsize=6, color='darkgreen', va='center')

for x, y in fiducials:
    circle = plt.Circle((x, y), 0.5, color='gold', ec='darkgoldenrod', linewidth=1.5, zorder=5)
    ax.add_patch(circle)
    ax.text(x, y - 1.2, 'FID', ha='center', va='top', fontsize=6, color='darkgoldenrod')

for x, y in mounting:
    circle = plt.Circle((x, y), 1.6, color='white', ec='black', linewidth=1.5, linestyle='--', zorder=5)
    ax.add_patch(circle)
    ax.text(x, y - 2.2, 'TH', ha='center', va='top', fontsize=6)

ax.set_xlim(25, 75)
ax.set_ylim(30, 70)
ax.set_aspect('equal')
ax.set_title('Bluetooth Module PCB — ai-probe-router Generated Layout\n40×30 mm | 7 nets | 9 testpoints | 3 fiducials | 2 tooling holes', fontsize=11)
ax.set_xlabel('X (mm)')
ax.set_ylabel('Y (mm)')
ax.grid(True, alpha=0.3)

from matplotlib.lines import Line2D

legend_elements = [
    Line2D([0], [0], marker='s', color='w', markerfacecolor='lightblue', markersize=10, label='Components'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='limegreen', markersize=10, label='Test Points'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='gold', markersize=8, label='Fiducials'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='white', markeredgecolor='black', markersize=10, label='Tooling Holes'),
    patches.Patch(facecolor='red', alpha=0.15, label='Keepout (Antenna)'),
]
ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

plt.tight_layout()
plt.savefig('bluetooth_module_layout.png', dpi=150, bbox_inches='tight')
print("Saved to bluetooth_module_layout.png")
plt.close()

# Also generate a schematic-style ASCII summary
print("\n" + "="*60)
print("  Bluetooth Module — Component Placement Summary")
print("="*60)
print("  Board: 40.0 x 30.0 mm")
print(f"  Original components: {len(original)}")
print(f"  Generated testpoints: {len(testpoints)}")
print(f"  Generated fiducials: {len(fiducials)}")
print(f"  Generated tooling holes: {len(mounting)}")
print(f"  Protection components: {len(protection)}")
print("="*60)
