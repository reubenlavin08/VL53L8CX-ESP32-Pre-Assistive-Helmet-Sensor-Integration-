"""
Re-analyse the v9 sweep through the wearable / latency lens.

Key question: what's the right (resolution, freq) config for a helmet-mounted
obstacle warning device on someone walking 1.0-1.5 m/s?

Outputs (visualizer/plots/):
  - wearable_latency_tradeoff.png  — frame latency × walking speed = blind-walk distance
  - wearable_noise_vs_latency.png   — σ on the y-axis, blind-walk distance on the x-axis
  - wearable_score.csv              — composite score for each config (lower = better)
"""

import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


VIS_DIR     = Path(__file__).parent
SUMMARY_CSV = VIS_DIR / "measurements.summary.csv"
PLOT_DIR    = VIS_DIR / "plots"
PLOT_DIR.mkdir(exist_ok=True)

# Wearable scenario parameters
WALK_MS_LOW  = 1.0     # slow walking pace m/s (cautious indoor)
WALK_MS_HIGH = 1.5     # brisk walking pace m/s
ALERT_REACTION_S = 0.5 # human reaction time after hearing the buzzer

# Load + parse
def load_summary():
    df = pd.read_csv(SUMMARY_CSV)
    pattern = re.compile(
        r"^(?P<short>[A-D]\d+)-(?P<res>\d+x\d+)-(?P<freq>\d+)hz-sharp(?P<sharp>\d+)"
        r"-(?P<order>closest|strongest|strict)-(?P<dist>\d+)cm-(?P<surface>\w+)$"
    )
    rows = []
    for _, row in df.iterrows():
        m = pattern.match(str(row['config']))
        if not m:
            continue
        try:
            sig = float(row['median_our_sigma_mm'])
        except (ValueError, TypeError):
            sig = float('nan')
        rows.append({
            'short':       m['short'],
            'resolution':  m['res'],
            'freq_hz':     int(m['freq']),
            'sharpener':   int(m['sharp']),
            'order_flag':  m['order'],
            'distance_cm': int(m['dist']),
            'our_sigma_mm':    sig,
        })
    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=['short', 'distance_cm'], keep='first')
    return out


def main():
    df = load_summary()
    # Focus on the most common knob combos at 48 cm (closest to per-row thresholds)
    base = df[(df['distance_cm'] == 48) & (df['order_flag'] == 'closest') & (df['sharpener'] == 5)].copy()
    base = base.sort_values(['resolution', 'freq_hz']).reset_index(drop=True)

    # Derived metrics
    # 1. Frame period in seconds
    base['frame_ms']      = 1000.0 / base['freq_hz']
    # 2. Walk-blind distance per frame at fast and slow walking
    base['blind_cm_fast'] = base['frame_ms'] / 1000.0 * (WALK_MS_HIGH * 100)
    base['blind_cm_slow'] = base['frame_ms'] / 1000.0 * (WALK_MS_LOW  * 100)
    # 3. Total reaction "blind zone" — frame latency + human reaction time, in cm
    base['react_cm_fast'] = base['blind_cm_fast'] + ALERT_REACTION_S * (WALK_MS_HIGH * 100)
    base['react_cm_slow'] = base['blind_cm_slow'] + ALERT_REACTION_S * (WALK_MS_LOW  * 100)
    # 4. Noise band at the alert threshold (4σ for 95% confidence)
    base['noise_band_cm'] = 4 * base['our_sigma_mm'] / 10.0

    # 5. Composite score: smaller is better.
    # We want low latency AND low noise. They scale differently —
    # latency in cm of walk-distance, noise in cm of measurement uncertainty.
    # Both penalise "things we will miss / be wrong about". Sum them.
    base['score_fast_cm'] = base['react_cm_fast'] + base['noise_band_cm']
    base['score_slow_cm'] = base['react_cm_slow'] + base['noise_band_cm']

    base = base[['short','resolution','freq_hz','our_sigma_mm','frame_ms',
                 'blind_cm_fast','noise_band_cm','react_cm_fast','score_fast_cm']]
    print(base.to_string(index=False))

    # === Plot: noise vs latency tradeoff ===
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = {'8x8': '#d35400', '4x4': '#2980b9'}
    markers = {10: 'o', 15: 's', 30: '^'}
    for _, row in base.iterrows():
        ax.scatter(row['blind_cm_fast'], row['noise_band_cm'],
                   s=180, color=colors[row['resolution']], marker=markers[row['freq_hz']],
                   edgecolors='black', linewidths=0.8, alpha=0.85,
                   label=f"{row['short']} ({row['resolution']} / {row['freq_hz']} Hz)")
        ax.annotate(f"  {row['short']}\n  {row['freq_hz']}Hz",
                    (row['blind_cm_fast'], row['noise_band_cm']),
                    fontsize=8, alpha=0.7)
    ax.set_xlabel(f"Blind-walk distance per frame at {WALK_MS_HIGH} m/s (cm) — LOWER = faster reaction")
    ax.set_ylabel("4σ measurement noise band (cm) — LOWER = tighter distance")
    ax.set_title("Wearable tradeoff: reaction time vs measurement noise\n"
                 f"(measured at d = 48 cm, walking @ {WALK_MS_HIGH} m/s, sharpener=5, CLOSEST)",
                 fontsize=11)
    ax.grid(True, alpha=0.3)
    # Pareto front annotation
    ax.text(0.55, 0.92,
            "Pareto-optimal = low on BOTH axes\n"
            "(towards bottom-left of plot)",
            transform=ax.transAxes, fontsize=9, va='top',
            bbox=dict(boxstyle='round', facecolor='#f0f0f0', alpha=0.8))
    # Compact legend
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='lower right', fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "wearable_noise_vs_latency.png", dpi=120, bbox_inches='tight')
    plt.close()

    # === Plot: composite score bar chart ===
    fig, ax = plt.subplots(figsize=(11, 6))
    labels = [f"{r['short']}\n{r['resolution']}/{r['freq_hz']}Hz" for _, r in base.iterrows()]
    pos = np.arange(len(labels))
    width = 0.4
    ax.bar(pos - width/2, base['react_cm_fast'], width,
           label=f"Reaction blind zone @ {WALK_MS_HIGH} m/s (cm)", color='#c0392b', alpha=0.85)
    ax.bar(pos + width/2, base['noise_band_cm'], width,
           label='4σ noise band (cm)', color='#2980b9', alpha=0.85)
    # Stacked total as line
    ax.plot(pos, base['score_fast_cm'], 'k--o', label='Total "blind zone" (sum)', markersize=8)
    ax.set_xticks(pos)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('cm')
    ax.set_title(f'Wearable composite score — lower = better\n'
                 f'(sum of reaction blind-zone + 4σ noise band, walking @ {WALK_MS_HIGH} m/s, d=48 cm)',
                 fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    ax.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "wearable_score.png", dpi=120, bbox_inches='tight')
    plt.close()

    # Save the score table
    base.to_csv(PLOT_DIR / "wearable_score.csv", index=False)
    print(f"\nSaved: {PLOT_DIR / 'wearable_noise_vs_latency.png'}")
    print(f"Saved: {PLOT_DIR / 'wearable_score.png'}")
    print(f"Saved: {PLOT_DIR / 'wearable_score.csv'}")

    # === Headline ===
    best_fast = base.loc[base['score_fast_cm'].idxmin()]
    print(f"\n=== Best config by composite score @ {WALK_MS_HIGH} m/s ===")
    print(f"  {best_fast['short']} ({best_fast['resolution']} @ {best_fast['freq_hz']} Hz)")
    print(f"  total blind zone = {best_fast['score_fast_cm']:.1f} cm")
    print(f"  (reaction = {best_fast['react_cm_fast']:.1f} cm, noise = {best_fast['noise_band_cm']:.2f} cm)")


if __name__ == "__main__":
    main()
