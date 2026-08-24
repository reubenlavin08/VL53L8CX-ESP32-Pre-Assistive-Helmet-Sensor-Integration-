"""Session report: turn flightlog sessions into the published metrics.

Usage:  python session_report.py [session_dir]     one session
        python session_report.py --all             every session + summary.csv

Outputs alerts/hour (spoken, non-query), FP votes/hour, FP rate
(votes / caution alerts), clip counts by trigger, median alert range.
Duration comes from heartbeats so a crash mid-walk still reports.
"""

import csv
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
SESS = HERE / "sessions"


def analyze(d):
    ev = []
    try:
        for line in (d / "events.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                ev.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except OSError:
        return None
    if not ev:
        return None
    t0 = ev[0]["t"]
    t1 = max((e["t"] for e in ev if e["e"] == "heartbeat"), default=ev[-1]["t"])
    hours = max((t1 - t0) / 3600.0, 1 / 3600.0)
    spoken = [e for e in ev if e["e"] == "spoken"]
    alerts = [e for e in spoken if e.get("tier") in ("caution", "directive")]
    cautions = [e for e in alerts if e["tier"] == "caution"]
    votes = [e for e in ev if e["e"] == "fp_vote"]
    clips = [e for e in ev if e["e"] == "clip"]
    ranges = [e["range_mm"] for e in alerts if e.get("range_mm")]
    clip_by = {}
    for c in clips:
        clip_by[c.get("trigger", "?")] = clip_by.get(c.get("trigger", "?"), 0) + 1
    mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e6
    return {
        "session": d.name,
        "duration_min": round((t1 - t0) / 60, 1),
        "spoken": len(spoken),
        "alerts": len(alerts),
        "alerts_per_hour": round(len(alerts) / hours, 1),
        "fp_votes": len(votes),
        "fp_per_hour": round(len(votes) / hours, 2),
        "fp_rate": round(len(votes) / len(cautions), 2) if cautions else 0.0,
        "median_alert_mm": int(statistics.median(ranges)) if ranges else None,
        "clips": clip_by,
        "disk_mb": round(mb, 1),
    }


def show(r):
    print(f"\n=== {r['session']} ===")
    for k, v in r.items():
        if k != "session":
            print(f"  {k:16} {v}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        r = analyze(pathlib.Path(sys.argv[1]))
        if r:
            show(r)
        return
    rows = []
    for d in sorted(SESS.iterdir()) if SESS.exists() else []:
        if d.is_dir():
            r = analyze(d)
            if r:
                show(r)
                rows.append(r)
    if rows:
        with open(SESS / "summary.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k != "clips"])
            w.writeheader()
            for r in rows:
                w.writerow({k: v for k, v in r.items() if k != "clips"})
        print(f"\nsummary.csv: {len(rows)} sessions")


if __name__ == "__main__":
    main()
