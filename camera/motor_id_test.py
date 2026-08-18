"""MOTOR ID TEST -- guided, spoken, zero-ambiguity mapping of GPIO -> skull.

    python camera/motor_id_test.py                      (host 192.168.1.228)

Fires each motor channel through the firmware's /api/motor endpoint (no
reflash, ranging keeps running), announces which channel is pulsing, and asks
where you felt it. Three questions later it prints the verdict and, if the
firmware's CENTER/RIGHT/LEFT aliases don't match physical reality, the EXACT
define lines to change in main/main.c.

Answers:  c = forehead/centre   r = right temple   l = left temple
          a = again (repulse)   q = quit
"""
import argparse
import json
import time
import urllib.request

CHANNELS = [(0, "channel 0  (GPIO 17, firmware alias CENTER)"),
            (1, "channel 1  (GPIO 18, firmware alias RIGHT)"),
            (2, "channel 2  (GPIO 8, firmware alias LEFT)")]
ALIAS = {0: "CENTER", 1: "RIGHT", 2: "LEFT"}
DEFINE = {0: "HAPTIC_GPIO_CENTER", 1: "HAPTIC_GPIO_RIGHT", 2: "HAPTIC_GPIO_LEFT"}
GPIO = {0: "GPIO_NUM_17", 1: "GPIO_NUM_18", 2: "GPIO_NUM_8"}
PLACE = {"c": "CENTER", "r": "RIGHT", "l": "LEFT"}


def say(text, rate=210):
    try:
        import pyttsx3
        e = pyttsx3.init()
        e.setProperty("rate", rate)
        e.say(text)
        e.runAndWait()
        e.stop()
    except Exception:
        pass


def pulse(host, i, duty, ms):
    url = f"http://{host}/api/motor?i={i}&duty={duty}&ms={ms}"
    with urllib.request.urlopen(url, timeout=6) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.1.228")
    ap.add_argument("--duty", type=int, default=220)
    ap.add_argument("--ms", type=int, default=500)
    args = ap.parse_args()

    print(__doc__)
    # connectivity check first, so a dead link fails loudly not confusingly
    try:
        with urllib.request.urlopen(f"http://{args.host}/api/health", timeout=4) as r:
            r.read()
        print(f"helmet reachable at {args.host}\n")
    except Exception as e:
        raise SystemExit(f"cannot reach the helmet at {args.host}: {e}\n"
                         "Is it powered and on WiFi?")

    result = {}
    for i, label in CHANNELS:
        print(f"--- {label} ---")
        while True:
            say(f"pulsing channel {i}")
            try:
                for _ in range(2):
                    pulse(args.host, i, args.duty, args.ms)
                    time.sleep(0.25)
            except Exception as e:
                print(f"  pulse failed: {e} -- check wiring on this channel")
            ans = input("  where did it buzz?  [c]entre / [r]ight / [l]eft / "
                        "[a]gain / [n]othing / [q]uit: ").strip().lower()
            if ans == "a":
                continue
            if ans == "q":
                return
            if ans == "n":
                result[i] = None
                print("  no buzz -- transistor/wiring issue on this channel, "
                      "flagged.\n")
                break
            if ans in PLACE:
                result[i] = PLACE[ans]
                print(f"  channel {i} -> {PLACE[ans]}\n")
                break
            print("  c, r, l, a, n or q please")

    print("=" * 56)
    dead = [i for i, v in result.items() if v is None]
    if dead:
        print(f"⚠ channels with NO buzz: {dead} -- fix wiring, rerun.")
    felt = {i: v for i, v in result.items() if v}
    if len(set(felt.values())) < len(felt):
        print("⚠ two channels mapped to the same place -- rerun, that can't be right.")
        return
    mismatches = [(i, v) for i, v in felt.items() if v != ALIAS[i]]
    if not mismatches:
        print("✅ PERFECT: physical layout matches the firmware aliases exactly.")
        print("   Nothing to change. The directional haptics are correctly mapped.")
        say("perfect mapping, nothing to change")
    else:
        print("Mapping differs from the firmware aliases. Change main/main.c to:")
        # invert: which GPIO ended up at each physical place
        gpio_at = {v: GPIO[i] for i, v in felt.items()}
        for place in ("CENTER", "RIGHT", "LEFT"):
            if place in gpio_at:
                print(f"   #define HAPTIC_GPIO_{place:<7} {gpio_at[place]}")
        print("then rebuild + reflash (or tell Claude, who will do it).")
        say("mapping recorded, firmware needs a small update")
    print("=" * 56)


if __name__ == "__main__":
    main()
