"""
Orthos Alpha - Cadence Detection Module
=========================================
Milestone: Automatic step detection and steps-per-minute calculation
from gyroscope signal using peak detection.

Biomechanical basis:
- Terminal stance / toe-off produces a gyroscope peak (shank angular
  velocity spikes as the limb accelerates into swing phase).
- Detecting these peaks and measuring inter-peak intervals gives us
  step timing directly, which yields cadence (steps/min) and lays the
  groundwork for stride variability (CV of inter-peak intervals).
- Reference: Salminen et al. (2024), Gait & Posture - shank angular
  velocity based 7-phase gait cycle segmentation.

Usage:
    python cadence_detection.py path/to/walk_log.csv
    python cadence_detection.py --demo    # runs on synthetic data

Expected CSV columns (auto-detected, case-insensitive, flexible naming):
    time column:  Time, Timestamp, time_ms, t
    gyro columns: GyroX, GyroY, GyroZ (deg/s) - or Gx, Gy, Gz

If your actual column headers differ, edit COLUMN_ALIASES below or
tell me the real headers and I'll adjust.
"""

import sys
import argparse
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, butter, filtfilt

# ----------------------------------------------------------------------
# Column name aliases - adjust here if your CSV headers differ
# ----------------------------------------------------------------------
COLUMN_ALIASES = {
    "time": ["time", "timestamp", "time_ms", "t", "millis"],
    "gyro_x": ["gyrox", "gx", "gyro_x"],
    "gyro_y": ["gyroy", "gy", "gyro_y"],
    "gyro_z": ["gyroz", "gz", "gyro_z"],
}


def _find_column(df, aliases):
    lower_map = {c.lower(): c for c in df.columns}
    # exact match first
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    # fall back to substring match (handles e.g. "gyroX_dps", "time_ms")
    for alias in aliases:
        for lower_name, orig_name in lower_map.items():
            if alias in lower_name:
                return orig_name
    return None


def load_and_resolve_columns(csv_path):
    df = pd.read_csv(csv_path)
    resolved = {}
    for key, aliases in COLUMN_ALIASES.items():
        col = _find_column(df, aliases)
        if col is None and key != "time":
            raise ValueError(
                f"Could not find a column for '{key}'. "
                f"Available columns: {list(df.columns)}. "
                f"Add the correct name to COLUMN_ALIASES['{key}']."
            )
        resolved[key] = col
    return df, resolved


def estimate_sample_rate(df, time_col, fallback_hz=50.0):
    """Estimate sample rate from timestamp column, or fall back to
    the known logging rate from Milestone 3 (50Hz)."""
    if time_col is None:
        print(f"[warn] No time column found - assuming {fallback_hz} Hz "
              f"(Milestone 3 logging rate).")
        return fallback_hz

    t = df[time_col].values.astype(float)
    dt = np.median(np.diff(t))

    # Heuristic: if values look like milliseconds, convert
    if dt > 1.0:  # likely ms
        fs = 1000.0 / dt
    else:  # likely seconds
        fs = 1.0 / dt

    if not np.isfinite(fs) or fs <= 0:
        print(f"[warn] Could not infer valid sample rate - assuming "
              f"{fallback_hz} Hz.")
        return fallback_hz

    return fs


def bandpass_filter(signal, fs, low=0.5, high=6.0, order=2):
    """Bandpass filter to isolate the gait-frequency band (~0.5-10 Hz)
    and remove drift + high-frequency sensor noise before peak picking."""
    nyq = 0.5 * fs
    low_n, high_n = low / nyq, min(high / nyq, 0.99)
    b, a = butter(order, [low_n, high_n], btype="band")
    return filtfilt(b, a, signal)


def compute_envelope(rectified_signal, fs, window_s=0.12):
    """
    Smooth the rectified (abs-value) signal into an envelope using a
    moving RMS window.

    Why: a single footfall isn't a clean impulse - it's a burst of
    oscillation lasting ~100-300ms (shank vibration, ringing from the
    bandpass filter, sensor noise). Peak-picking the raw rectified
    signal directly often finds 2-4 sub-peaks inside one footfall's
    burst, or lets one large amplitude sample skew a global threshold.
    A moving-RMS envelope collapses each burst into a single smooth
    hump, so peak-picking finds one peak per footfall instead of
    several, and is far less sensitive to a single outlier sample.

    window_s=0.12 (120ms) is chosen to be shorter than the minimum
    plausible inter-step interval (~250ms, capping at 240 spm) so
    adjacent footfalls don't get smeared into each other, but long
    enough to average out a single-sample transient.
    """
    window_samples = max(int(window_s * fs), 1)
    # Moving RMS via convolution: sqrt(moving average of squared signal)
    kernel = np.ones(window_samples) / window_samples
    envelope = np.sqrt(np.convolve(rectified_signal ** 2, kernel, mode="same"))
    return envelope


def detect_steps(gyro_signal, fs, min_step_interval_s=0.25):
    """
    Detect steps via peak detection on a smoothed envelope of the
    gyroscope signal.

    min_step_interval_s: minimum plausible time between steps.
        0.25s -> caps cadence detection at 240 steps/min, well above
        elite running cadence (~180-200 spm), preventing noise from
        being double-counted as steps.
    """
    filtered = bandpass_filter(gyro_signal, fs)
    rectified = np.abs(filtered)
    envelope = compute_envelope(rectified, fs)

def calibrate_noise_floor(quiet_gyro_signal, fs, margin=1.5):
    """
    Compute an absolute noise-floor threshold from a known quiet-stance
    recording (e.g. the firmware's own "Stand STILL, calibrating..."
    phase at the start of every session).

    Why this is necessary and percentile/MAD-based thresholds alone
    are not: those are self-referencing - computed from the same
    window they're applied to. On a genuinely flat/idle signal, the
    median and MAD both collapse toward zero right along with the
    noise, so the adaptive threshold collapses too and starts treating
    tiny sensor noise as steps (confirmed: 16 false "steps" detected
    on a real 10s idle segment at threshold ~0). An absolute floor
    anchored to a known-quiet reference recording doesn't have this
    problem, because it isn't computed from the segment being analyzed.

    margin=1.5 leaves headroom above the single largest bump observed
    during quiet stance, so ordinary calibration-phase settling
    doesn't false-trigger, without being so high it could suppress
    real low-amplitude footfalls (which run an order of magnitude
    higher in the data checked so far).
    """
    filtered = bandpass_filter(quiet_gyro_signal, fs)
    envelope = compute_envelope(np.abs(filtered), fs)
    return float(np.max(envelope) * margin)


# Fallback absolute floor (envelope units, deg/s) if no quiet-stance
# calibration segment is available for this session. Derived from one
# real Orthos quiet-stance recording (peak envelope ~8.5) with the same
# margin used in calibrate_noise_floor(). This is a stopgap, not a
# substitute for calibrating per-device/per-session: sensor noise floor
# can vary with individual MPU6050 units and mounting.
DEFAULT_NOISE_FLOOR = 12.0


def detect_steps(gyro_signal, fs, min_step_interval_s=0.25, noise_floor=None):
    """
    Detect steps via peak detection on a smoothed envelope of the
    gyroscope signal.

    min_step_interval_s: minimum plausible time between steps.
        0.25s -> caps cadence detection at 240 steps/min, well above
        elite running cadence (~180-200 spm), preventing noise from
        being double-counted as steps.
    noise_floor: absolute envelope-amplitude floor from
        calibrate_noise_floor(), ideally computed from this session's
        own quiet-stance calibration recording. Falls back to
        DEFAULT_NOISE_FLOOR with a warning if not provided.
    """
    filtered = bandpass_filter(gyro_signal, fs)
    rectified = np.abs(filtered)
    envelope = compute_envelope(rectified, fs)

    min_distance_samples = int(min_step_interval_s * fs)

    if noise_floor is None:
        print(f"[warn] No quiet-stance noise floor provided - falling back "
              f"to DEFAULT_NOISE_FLOOR={DEFAULT_NOISE_FLOOR}. For reliable "
              f"results, pass the session's own calibration-phase data "
              f"through calibrate_noise_floor().")
        noise_floor = DEFAULT_NOISE_FLOOR

    # Adaptive component (scales with this session's own amplitude, so
    # it self-calibrates for stride style/speed) combined with the
    # absolute noise floor (protects against a flat/idle segment being
    # analyzed, where the adaptive component alone would collapse to
    # near-zero and start counting noise as steps).
    threshold = max(0.8 * np.percentile(envelope, 50), noise_floor)

    peaks, properties = find_peaks(
        envelope,
        distance=max(min_distance_samples, 1),
        height=threshold,
        prominence=threshold * 0.7,
    )
    return peaks, filtered, envelope


def compute_cadence(peak_indices, fs, window_s=None, total_samples=None):
    """
    Compute cadence (steps/min) and stride timing.

    If window_s is provided, also returns a rolling cadence over time
    windows (useful for spotting fatigue-related cadence drift within
    a single session).
    """
    if len(peak_indices) < 2:
        return {
            "step_count": len(peak_indices),
            "overall_cadence_spm": None,
            "stride_intervals_s": np.array([]),
            "mean_stride_interval_s": None,
            "stride_cv_percent": None,
        }

    step_times_s = peak_indices / fs
    duration_s = step_times_s[-1] - step_times_s[0]
    step_count = len(peak_indices)

    # Cadence = steps per minute over the active walking duration
    overall_cadence = (step_count - 1) / duration_s * 60.0

    stride_intervals = np.diff(step_times_s)
    mean_interval = np.mean(stride_intervals)
    cv_percent = (np.std(stride_intervals) / mean_interval) * 100.0

    return {
        "step_count": step_count,
        "overall_cadence_spm": round(overall_cadence, 1),
        "stride_intervals_s": stride_intervals,
        "mean_stride_interval_s": round(mean_interval, 3),
        "stride_cv_percent": round(cv_percent, 2),  # bonus: this is
        # also your stride-variability metric, same peak data reused
    }


def analyze_csv(csv_path, gyro_axis="gyro_z", quiet_csv_path=None):
    df, cols = load_and_resolve_columns(csv_path)
    fs = estimate_sample_rate(df, cols["time"])

    noise_floor = None
    if quiet_csv_path:
        quiet_df, quiet_cols = load_and_resolve_columns(quiet_csv_path)
        quiet_signal = quiet_df[quiet_cols[gyro_axis]].values.astype(float)
        noise_floor = calibrate_noise_floor(quiet_signal, fs)
        print(f"Calibrated noise floor from {quiet_csv_path}: {noise_floor:.1f}")

    signal = df[cols[gyro_axis]].values.astype(float)
    peaks, filtered, envelope = detect_steps(signal, fs, noise_floor=noise_floor)
    results = compute_cadence(peaks, fs)

    print(f"\n--- Orthos Cadence Analysis: {csv_path} ---")
    print(f"Sample rate:         {fs:.1f} Hz")
    print(f"Signal used:         {cols[gyro_axis]}")
    print(f"Steps detected:      {results['step_count']}")
    print(f"Cadence:             {results['overall_cadence_spm']} steps/min")
    print(f"Mean stride interval:{results['mean_stride_interval_s']} s")
    print(f"Stride CV:           {results['stride_cv_percent']}%  "
          f"(<5% = normal, >8-10% = elevated fall/fatigue risk per lit.)")
    return results, peaks, filtered, envelope, fs


def run_demo():
    """Synthetic gait signal self-test - validates the algorithm logic
    without needing real hardware data. ~110 steps/min cadence,
    realistic stride variability injected."""
    print("Running self-test on synthetic gait signal...")
    fs = 50.0
    duration_s = 30
    n = int(fs * duration_s)
    t = np.arange(n) / fs

    target_cadence_spm = 112
    step_interval = 60.0 / target_cadence_spm

    rng = np.random.default_rng(42)
    step_times = []
    current = 0.5
    while current < duration_s - 0.5:
        step_times.append(current)
        # inject ~4% stride-time variability, realistic for healthy gait
        current += step_interval * (1 + rng.normal(0, 0.04))

    signal = np.zeros(n) + rng.normal(0, 5, n)  # sensor noise floor
    for st in step_times:
        idx = int(st * fs)
        # Realistic toe-off gyro spike: ~150-200ms wide (7-10 samples
        # at 50Hz), not a single-sample impulse. A too-narrow synthetic
        # pulse has broadband energy that rings through a bandpass
        # filter and gets miscounted as extra peaks.
        width = 8
        for k in range(-width, width + 1):
            if 0 <= idx + k < n:
                signal[idx + k] += 180 * np.exp(-0.5 * (k / 3.5) ** 2)

    # Synthesize a quiet-stance calibration segment (same noise floor,
    # no steps) so the self-test exercises the real calibrate_noise_floor()
    # path rather than silently relying on the DEFAULT_NOISE_FLOOR fallback.
    quiet_signal = rng.normal(0, 5, int(fs * 5))
    noise_floor = calibrate_noise_floor(quiet_signal, fs)
    print(f"Calibrated noise floor from synthetic quiet-stance segment: {noise_floor:.1f}")

    peaks, filtered, envelope = detect_steps(signal, fs, noise_floor=noise_floor)
    results = compute_cadence(peaks, fs)

    print(f"\nGround truth:  {len(step_times)} steps, "
          f"{target_cadence_spm} steps/min target")
    print(f"Detected:      {results['step_count']} steps, "
          f"{results['overall_cadence_spm']} steps/min")
    print(f"Stride CV:     {results['stride_cv_percent']}% "
          f"(injected ~4%)")

    error_pct = abs(results['overall_cadence_spm'] - target_cadence_spm) / target_cadence_spm * 100
    print(f"\nCadence error vs ground truth: {error_pct:.1f}%")
    if error_pct < 5:
        print("PASS - algorithm within 5% of ground truth cadence.")
    else:
        print("CHECK - error exceeds 5%, review threshold/filter params.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orthos cadence detection")
    parser.add_argument("csv_path", nargs="?", help="Path to gait CSV log")
    parser.add_argument("--demo", action="store_true",
                         help="Run self-test on synthetic data")
    parser.add_argument("--axis", default="gyro_z",
                         choices=["gyro_x", "gyro_y", "gyro_z"],
                         help="Which gyro axis to use for step detection "
                              "(default gyro_z - typically sagittal-plane "
                              "rotation for shin-mounted sensor, adjust "
                              "based on your mounting orientation)")
    parser.add_argument("--quiet-csv", default=None,
                         help="Path to a quiet-stance CSV (same columns) "
                              "used to calibrate the absolute noise floor "
                              "for this device/session. Strongly recommended - "
                              "without it, a fallback default is used which "
                              "may not match your specific sensor's noise.")
    args = parser.parse_args()

    if args.demo or not args.csv_path:
        run_demo()
    else:
        analyze_csv(args.csv_path, gyro_axis=args.axis, quiet_csv_path=args.quiet_csv)
