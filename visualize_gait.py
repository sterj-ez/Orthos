"""
Orthos Alpha — Gait Visualization Script
Milestone 3: First Walking Test
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# ── Config ───────────────────────────────────────────────────────────────────

CSV_PATH = r"C:\Users\ezste\Downloads\walking_test_01.csv"

WALK_START_MS = 37000
WALK_END_MS   = 59000

# ── Load Data ─────────────────────────────────────────────────────────────────

print(f"Loading {CSV_PATH}...")

rows = []
with open(CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        line = line.strip('"')
        parts = line.split(",")
        if len(parts) != 7:
            continue
        try:
            values = [float(p) for p in parts]
            if values[0] >= 0:  # valid timestamp
                rows.append(values)
        except ValueError:
            continue

if len(rows) == 0:
    print("\nERROR: No valid rows found.")
    print("Open your CSV and check it looks like:")
    print("  20,-0.001,0.000,1.001,-3.60,1.19,1.16")
    exit(1)

df = pd.DataFrame(rows, columns=[
    "time_ms", "accelX_g", "accelY_g", "accelZ_g",
    "gyroX_dps", "gyroY_dps", "gyroZ_dps"
])

print(f"  Loaded {len(df)} samples")
print(f"  Time range: {df['time_ms'].min():.0f}ms – {df['time_ms'].max():.0f}ms "
      f"({(df['time_ms'].max() - df['time_ms'].min()) / 1000:.1f}s)")

df["time_s"] = df["time_ms"] / 1000.0
df["accel_magnitude"] = np.sqrt(df["accelX_g"]**2 + df["accelY_g"]**2 + df["accelZ_g"]**2)
df["gyro_magnitude"]  = np.sqrt(df["gyroX_dps"]**2 + df["gyroY_dps"]**2 + df["gyroZ_dps"]**2)

# ── Trim to walking window ────────────────────────────────────────────────────

walk_df = df[(df["time_ms"] >= WALK_START_MS) & (df["time_ms"] <= WALK_END_MS)].copy()
print(f"  Walking window: {len(walk_df)} samples")

if len(walk_df) == 0:
    print("\nERROR: Walking window is empty.")
    print(f"Your data runs {df['time_ms'].min():.0f}ms – {df['time_ms'].max():.0f}ms")
    print("Adjust WALK_START_MS and WALK_END_MS to match your data range.")
    exit(1)

walk_s = walk_df["time_s"].values

# ── Plot ──────────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(16, 12))
fig.suptitle("Orthos Alpha — Walking Test 01\nGait Signal Visualization",
             fontsize=16, fontweight="bold", y=0.98)

gs = gridspec.GridSpec(4, 1, hspace=0.45, top=0.93, bottom=0.07)

ax1 = fig.add_subplot(gs[0])
ax1.plot(walk_s, walk_df["accelZ_g"], color="#2196F3", linewidth=0.8, label="AccelZ (vertical)")
ax1.axhline(y=1.0, color="gray", linestyle="--", linewidth=0.6, alpha=0.5, label="1g baseline")
ax1.set_ylabel("g-force", fontsize=10)
ax1.set_title("Vertical Acceleration (AccelZ) — Foot Strike Events", fontsize=11)
ax1.legend(loc="upper right", fontsize=8)
ax1.set_xlim(walk_s[0], walk_s[-1])
ax1.grid(True, alpha=0.3)

ax2 = fig.add_subplot(gs[1])
ax2.plot(walk_s, walk_df["gyroY_dps"], color="#E91E63", linewidth=0.8, label="GyroY (flex/extend)")
ax2.plot(walk_s, walk_df["gyroX_dps"], color="#FF9800", linewidth=0.6, alpha=0.6, label="GyroX (abduction)")
ax2.axhline(y=0, color="gray", linestyle="--", linewidth=0.6, alpha=0.5)
ax2.set_ylabel("deg/sec", fontsize=10)
ax2.set_title("Gyroscope — Leg Rotation (Stride Rhythm)", fontsize=11)
ax2.legend(loc="upper right", fontsize=8)
ax2.set_xlim(walk_s[0], walk_s[-1])
ax2.grid(True, alpha=0.3)

ax3 = fig.add_subplot(gs[2])
ax3.plot(walk_s, walk_df["accel_magnitude"], color="#4CAF50", linewidth=0.8, label="|Accel|")
ax3.axhline(y=1.0, color="gray", linestyle="--", linewidth=0.6, alpha=0.5, label="1g (standing)")
ax3.fill_between(walk_s, 1.0, walk_df["accel_magnitude"],
                 where=(walk_df["accel_magnitude"] > 1.05),
                 color="#4CAF50", alpha=0.25, label="Impact events")
ax3.set_ylabel("g-force", fontsize=10)
ax3.set_title("Total Acceleration Magnitude — Impact Events", fontsize=11)
ax3.legend(loc="upper right", fontsize=8)
ax3.set_xlim(walk_s[0], walk_s[-1])
ax3.grid(True, alpha=0.3)

ax4 = fig.add_subplot(gs[3])
ax4.plot(walk_s, walk_df["gyro_magnitude"], color="#9C27B0", linewidth=0.8, label="|Gyro|")
ax4.fill_between(walk_s, 0, walk_df["gyro_magnitude"], color="#9C27B0", alpha=0.15)
ax4.set_ylabel("deg/sec", fontsize=10)
ax4.set_xlabel("Time (seconds)", fontsize=10)
ax4.set_title("Total Gyroscope Magnitude — Rotational Activity", fontsize=11)
ax4.legend(loc="upper right", fontsize=8)
ax4.set_xlim(walk_s[0], walk_s[-1])
ax4.grid(True, alpha=0.3)

# ── Stats ─────────────────────────────────────────────────────────────────────

duration_s = (WALK_END_MS - WALK_START_MS) / 1000
sample_rate = len(walk_df) / duration_s

print(f"\n── Walking Session Stats ──────────────────────")
print(f"  Duration:       {duration_s:.1f}s")
print(f"  Sample rate:    {sample_rate:.1f} Hz")
print(f"  AccelZ range:   {walk_df['accelZ_g'].min():.3f}g to {walk_df['accelZ_g'].max():.3f}g")
print(f"  GyroY range:    {walk_df['gyroY_dps'].min():.1f} to {walk_df['gyroY_dps'].max():.1f} deg/s")
print(f"  Peak magnitude: {walk_df['accel_magnitude'].max():.3f}g")
print(f"──────────────────────────────────────────────\n")

output_path = r"C:\Users\ezste\Downloads\walking_test_01_plot.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
print(f"Plot saved to: {output_path}")

plt.show()