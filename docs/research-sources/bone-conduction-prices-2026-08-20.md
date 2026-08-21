# Bone-conduction headset — verified Canadian prices (partial) — 2026-08-20

Status: PARTIAL. Amazon.ca blocked automated price checks (bot detection);
the research agent correctly declined to bypass it via proxy, so Amazon
prices/shipping and the budget brands (Mojawa, Vidonn, H2O) remain
UNVERIFIED. Clean route to finish: the Chrome extension driving Reuben's
own logged-in browser (2 minutes, when he's at the keyboard). The full
buying guide (latency/codec, mic, wired 3.5mm options, top-3 rec) is in
the feasibility pack still being synthesized.

## Verified at Canada Computers (CAD, 2026-08-20)

| Model | Price | Note |
|---|---|---|
| **Shokz OpenMove** | **$99.99** | Only name-brand bone-conduction under $120 |
| Shokz OpenRun | $169.99 | |
| Shokz OpenRun Pro 2 | $249.99 | |

## Traps

- **Shokz's own /en-ca pages display USD** despite the Canadian URL — do
  not read those as CAD prices.
- Any third-party price aggregator that "worked around" Amazon's block is
  untrustworthy; treat as unverified.

## Final recommendation — SUPERSEDED the interim OpenMove pick

The full buying guide ([[feasibility-pack-2026-08-20]] §6) reversed this:
**do NOT buy the OpenMove** (SBC-only ≈ 260 ms jittery latency — a
head-tracked tick lands ~23° off during a turn; rear band decouples from
the helmet IMU). Instead:

- **Spatial ticks: DIY wired** — Dayton BCE-1 exciter $76.00
  (Amazon.ca B00HFG6AZG) or 2× generic BC drivers $16.62 ea
  (B0CZ7HJBVW) + PAM8403 amp; bonded to the shell = zero latency, known
  pose vs the BNO085.
- **Speech/menus: Soundcore V30i $44.99** (B0CNCHLR56, open-ear
  ear-hook, no rear band).
- Suggested combo: **V30i + 2 drivers ≈ $78 total.**
