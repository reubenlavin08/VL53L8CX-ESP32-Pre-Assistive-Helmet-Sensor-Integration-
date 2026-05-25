"""
Analysis of VL53L8CX tuning sweep data.

Reads:
  - measurements.summary.csv  (one row per config-per-distance)
  - raw_frames/*.csv           (per-frame distance + sigma + status per zone)

Outputs plots to: plots/
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


VIS_DIR     = Path(__file__).parent
SUMMARY_CSV = VIS_DIR / "measurements.summary.csv"
RAW_DIR     = VIS_DIR / "raw_frames"
PLOT_DIR    = VIS_DIR / "plots"


def load_summary():
    """Parse summary CSV into a tidy DataFrame with one row per config-per-distance."""
    df = pd.read_csv(SUMMARY_CSV)
    # Filter only sweep rows: e.g. "A1-8x8-10hz-sharp0-closest-48cm-blackfoam"
    pattern = re.compile(
        r"^(?P<short>[A-D]\d+)"
        r"-(?P<res>\d+x\d+)"
        r"-(?P<freq>\d+)hz"
        r"-sharp(?P<sharp>\d+)"
        r"-(?P<order>closest|strongest|strict)"
        r"-(?P<dist>\d+)cm-(?P<surface>\w+)$"
    )
    rows = []
    for _, row in df.iterrows():
        m = pattern.match(str(row['config']))
        if not m:
            continue
        rows.append({
            'short':       m['short'],
            'resolution':  m['res'],
            'freq_hz':     int(m['freq']),
            'sharpener':   int(m['sharp']),
            'order_flag':  m['order'],          # closest / strongest / strict
            'distance_cm': int(m['dist']),
            'surface':     m['surface'],
            'our_sigma_mm':    float(row['median_our_sigma_mm'])   if row['median_our_sigma_mm']    else np.nan,
            'sensor_sigma_mm': float(row['median_sensor_sigma_mm']) if row['median_sensor_sigma_mm'] else np.nan,
            'yield_pct':       float(row['overall_valid_yield']) * 100,
            'zones':           int(row['zones_reporting']),
        })
    out = pd.DataFrame(rows)
    # If duplicates exist (retry that completed twice), keep first
    out = out.drop_duplicates(subset=['short', 'distance_cm'], keep='first')
    return out


# ── Layer 1 plots: aggregate trends ─────────────────────────────────────────

def plot_sigma_vs_distance(df):
    """Line per config — confirms σ ∝ distance scaling."""
    fig, ax = plt.subplots(figsize=(11, 7))
    colors_a = plt.cm.Oranges(np.linspace(0.4, 0.9, 6))
    colors_b = plt.cm.Blues(np.linspace(0.3, 0.95, 9))
    colors_cd = {'C1': 'red', 'D1': 'purple'}

    a_count = 0
    b_count = 0
    for short, group in df.groupby('short'):
        group = group.sort_values('distance_cm')
        if short.startswith('A'):
            color = colors_a[a_count]; marker = 'o'; a_count += 1
        elif short.startswith('B'):
            color = colors_b[b_count]; marker = 's'; b_count += 1
        else:
            color = colors_cd.get(short, 'gray'); marker = '^'

        label = f"{short} ({group.iloc[0]['resolution']}/{group.iloc[0]['freq_hz']}Hz/s{group.iloc[0]['sharpener']})"
        ax.plot(group['distance_cm'], group['our_sigma_mm'],
                marker + '-', color=color, label=label, alpha=0.85, markersize=7)

    # Add the theoretical linear prediction line, anchored at 48cm A1
    a1_48 = df[(df['short'] == 'A1') & (df['distance_cm'] == 48)]['our_sigma_mm'].iloc[0]
    dists = np.array([48, 68, 89])
    ax.plot(dists, a1_48 * dists / 48, 'k--', alpha=0.4,
            label='σ ∝ distance (theory)', linewidth=1.5)

    ax.set_xlabel('Target distance d (cm)')
    ax.set_ylabel('Median per-zone σ (mm), 200-frame cross-frame stdev')
    ax.set_title('Fig 1. Distance noise scaling across all 17 sensor configurations\n'
                 '(black foam target, n = 200 frames per (config, distance) cell)',
                 fontsize=11)
    ax.legend(ncol=2, fontsize=7.5, loc='upper left', title='Config (res / freq / sharpener)', title_fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xticks([48, 68, 89])
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "layer1_sigma_vs_distance.png", dpi=120, bbox_inches='tight')
    plt.close()


def plot_heatmap(df):
    """Heatmap: config × distance, colored by σ."""
    pivot = df.pivot(index='short', columns='distance_cm', values='our_sigma_mm')
    pivot = pivot.reindex(sorted(pivot.index, key=lambda s: (s[0], int(s[1:]))))
    fig, ax = plt.subplots(figsize=(7, 9))
    sns.heatmap(pivot, annot=True, fmt='.2f', cmap='YlOrRd',
                ax=ax, cbar_kws={'label': 'Median per-zone σ (mm)'})
    ax.set_xlabel('Target distance d (cm)')
    ax.set_ylabel('Config')
    ax.set_title('Fig 2. Cross-config noise comparison\n'
                 '(median σ per (config, distance), black foam, n=200)',
                 fontsize=11)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "layer1_heatmap.png", dpi=120, bbox_inches='tight')
    plt.close()


def plot_knob_impact(df):
    """Three subplots isolating the effect of each tunable knob (one-at-a-time)."""
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))

    # (a) Resolution comparison @ 10Hz, sharp=5 across distances
    ax = axes[0]
    cmp = df[(df['freq_hz'] == 10) & (df['sharpener'] == 5) & (df['order_flag'] == 'closest')]
    for res, g in cmp.groupby('resolution'):
        g = g.sort_values('distance_cm')
        ax.plot(g['distance_cm'], g['our_sigma_mm'], 'o-', label=res, markersize=10, linewidth=2)
    ax.set_xlabel('Target distance d (cm)')
    ax.set_ylabel('Median σ (mm)')
    ax.set_title('(a) Resolution effect\n(held: f = 10 Hz, sharpener = 5)', fontsize=10)
    ax.legend(title='Zone grid')
    ax.grid(True, alpha=0.3)
    ax.set_xticks([48, 68, 89])

    # (b) Frequency effect @ 4x4, sharp=5
    ax = axes[1]
    cmp = df[(df['resolution'] == '4x4') & (df['sharpener'] == 5) & (df['order_flag'] == 'closest')]
    for f, g in cmp.groupby('freq_hz'):
        g = g.sort_values('distance_cm')
        ax.plot(g['distance_cm'], g['our_sigma_mm'], 'o-', label=f"{f} Hz", markersize=10, linewidth=2)
    ax.set_xlabel('Target distance d (cm)')
    ax.set_ylabel('Median σ (mm)')
    ax.set_title('(b) Ranging frequency effect\n(held: 4×4 grid, sharpener = 5)', fontsize=10)
    ax.legend(title='Frame rate')
    ax.grid(True, alpha=0.3)
    ax.set_xticks([48, 68, 89])

    # (c) Sharpener effect @ 8x8, 10Hz
    ax = axes[2]
    cmp = df[(df['resolution'] == '8x8') & (df['freq_hz'] == 10) & (df['order_flag'] == 'closest')]
    for s, g in cmp.groupby('sharpener'):
        g = g.sort_values('distance_cm')
        ax.plot(g['distance_cm'], g['our_sigma_mm'], 'o-',
                label=f"{s}%", markersize=10, linewidth=2)
    ax.set_xlabel('Target distance d (cm)')
    ax.set_ylabel('Median σ (mm)')
    ax.set_title('(c) Edge-sharpener effect\n(held: 8×8 grid, f = 10 Hz)', fontsize=10)
    ax.legend(title='Sharpener %')
    ax.grid(True, alpha=0.3)
    ax.set_xticks([48, 68, 89])

    fig.suptitle('Fig 3. Isolated knob-impact studies (one-factor-at-a-time, '
                 'black foam target, n = 200 frames per point)',
                 fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "layer1_knob_impact.png", dpi=120, bbox_inches='tight')
    plt.close()


def plot_our_vs_sensor_sigma(df):
    """Does the sensor's own sigma_mm estimate match the observed sigma?"""
    fig, ax = plt.subplots(figsize=(8, 8))
    for short, g in df.groupby('short'):
        ax.scatter(g['sensor_sigma_mm'], g['our_sigma_mm'], label=short, s=80, alpha=0.7)
    # 1:1 reference line
    lim = max(df['our_sigma_mm'].max(), df['sensor_sigma_mm'].max()) * 1.05
    ax.plot([0, lim], [0, lim], 'k--', alpha=0.4, label='1:1')
    ax.set_xlabel("Sensor's self-reported sigma_mm (median across zones)")
    ax.set_ylabel("Empirical σ (cross-frame stdev, median across zones, mm)")
    ax.set_title("Fig 4. Sensor self-calibration check\n"
                 "(does range_sigma_mm reported by the sensor match the actual cross-frame variability?)",
                 fontsize=11)
    ax.legend(fontsize=7, ncol=2, title='Config', title_fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "layer1_our_vs_sensor_sigma.png", dpi=120, bbox_inches='tight')
    plt.close()


# ── Layer 2: per-zone spatial maps ──────────────────────────────────────────

def _load_raw(target_short, distance_cm):
    """Find raw frame file for (config_short, distance) and return DataFrame."""
    matches = sorted(RAW_DIR.glob(f"{target_short}-*-{distance_cm}cm-blackfoam_*.csv"))
    if not matches:
        return None, None
    df = pd.read_csv(matches[0])
    n_zones = sum(1 for c in df.columns if c.startswith('dist_z'))
    return df, n_zones


def plot_per_zone_sigma(distance_cm, targets):
    """4-panel grid: per-zone σ heatmap for selected configs."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    for ax, short in zip(axes.flat, targets):
        df, n_zones = _load_raw(short, distance_cm)
        if df is None:
            ax.text(0.5, 0.5, f'no raw data for {short}', ha='center', transform=ax.transAxes)
            ax.axis('off')
            continue
        side = int(np.sqrt(n_zones))
        dist_cols = [f'dist_z{z}' for z in range(n_zones)]
        dists = df[dist_cols].values.astype(float)
        dists[dists >= 4000] = np.nan
        zone_sigma = np.nanstd(dists, axis=0, ddof=1).reshape(side, side)
        sns.heatmap(zone_sigma, annot=True, fmt='.1f', cmap='YlOrRd',
                    ax=ax, cbar_kws={'label': 'σ (mm)'})
        ax.set_title(f"{short} — per-zone σ", fontsize=11)
        ax.set_xlabel('Column (left → right)')
        ax.set_ylabel('Row (top → bottom)')
    fig.suptitle(f'Fig 5. Per-zone σ spatial maps at d = {distance_cm} cm '
                 f'(4 representative configs, n = 200 frames each)',
                 fontsize=12, y=1.00)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / f"layer2_per_zone_sigma_{distance_cm}cm.png", dpi=120, bbox_inches='tight')
    plt.close()


def plot_per_zone_mean(distance_cm, target='A1'):
    """Per-zone mean distance — reveals sensor tilt as vertical gradient."""
    df, n_zones = _load_raw(target, distance_cm)
    if df is None:
        print(f"No raw data for {target} at {distance_cm}cm")
        return
    side = int(np.sqrt(n_zones))
    dist_cols = [f'dist_z{z}' for z in range(n_zones)]
    dists = df[dist_cols].values.astype(float)
    dists[dists >= 4000] = np.nan
    zone_mean = np.nanmean(dists, axis=0).reshape(side, side)

    fig, ax = plt.subplots(figsize=(9, 8))
    sns.heatmap(zone_mean, annot=True, fmt='.0f', cmap='viridis',
                ax=ax, cbar_kws={'label': 'Mean reported distance (mm)'})
    # Annotate: vertical gradient = sensor tilt evidence
    top_row_mean = np.nanmean(zone_mean[0, :])
    bot_row_mean = np.nanmean(zone_mean[-1, :])
    gradient = bot_row_mean - top_row_mean
    ax.set_title(f"Fig 6. Per-zone mean distance ({target}) at d = {distance_cm} cm — mount-tilt diagnostic\n"
                 f"Top-row mean = {top_row_mean:.0f} mm | Bottom-row mean = {bot_row_mean:.0f} mm | "
                 f"vertical Δ = {gradient:+.0f} mm  →  consistent with ~5–10° downward sensor tilt",
                 fontsize=10)
    ax.set_xlabel('Column (left → right)')
    ax.set_ylabel('Row (top → bottom)')
    plt.tight_layout()
    plt.savefig(PLOT_DIR / f"layer2_per_zone_mean_{target}_{distance_cm}cm.png", dpi=120, bbox_inches='tight')
    plt.close()


def main():
    PLOT_DIR.mkdir(exist_ok=True)
    df = load_summary()
    print(f"Loaded {len(df)} sweep rows from {SUMMARY_CSV.name}")
    print(f"Configs: {sorted(df['short'].unique())}")
    print(f"Distances: {sorted(df['distance_cm'].unique())} cm\n")

    print("Layer 1.1 — sigma vs distance ...")
    plot_sigma_vs_distance(df)

    print("Layer 1.2 — heatmap ...")
    plot_heatmap(df)

    print("Layer 1.3 — knob impact ...")
    plot_knob_impact(df)

    print("Layer 1.4 — our sigma vs sensor's reported sigma ...")
    plot_our_vs_sensor_sigma(df)

    print("Layer 2.1 — per-zone sigma heatmaps at 48 cm ...")
    plot_per_zone_sigma(48, ['A1', 'A2', 'B2', 'D1'])
    plot_per_zone_sigma(89, ['A1', 'A2', 'B2', 'D1'])

    print("Layer 2.2 — per-zone mean distance (tilt check) at 48 cm ...")
    plot_per_zone_mean(48, 'A1')
    plot_per_zone_mean(89, 'A1')

    print(f"\nAll plots saved to: {PLOT_DIR.resolve()}")


if __name__ == "__main__":
    main()
