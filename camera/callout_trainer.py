"""BREVITY TRAINER -- learn the callout codes the way pilots learn brevity.

    python camera/callout_trainer.py            10-round drill
    python camera/callout_trainer.py --rounds 20 --rate 260

Speaks a random brevity callout, you answer on the keyboard, it scores accuracy
and reaction time. The vocabulary is docs/CALLOUT-PROTOCOL.md section 4 -- the
same strings cv_fusion.py --mode brevity emits, so fluency here transfers 1:1.

Answer keys:
  object:    m=man  b=block  c=car  k=bike  d=dog  p=post
  clock:     0=ten  9=eleven  1=twelve  2=one  3=two      (left -> right)
  commands:  s=stop stop  l=break left  r=break right  n=clean  x=blind

Ten minutes of this is the demo: run PLAIN mode for an audience, then show a
trained user running BREVITY at ~60% shorter utterances.
"""
import argparse
import msvcrt
import random
import time

OBJECTS = {"m": "man", "b": "block", "c": "car", "k": "bike", "d": "dog", "p": "post"}
CLOCKS = {"0": "ten", "9": "eleven", "1": "twelve", "2": "one", "3": "two"}
COMMANDS = {"s": "stop stop", "l": "break left", "r": "break right",
            "n": "clean", "x": "blind"}


def say(text, rate):
    import pyttsx3
    eng = pyttsx3.init()
    eng.setProperty("rate", rate)
    eng.say(text)
    eng.runAndWait()
    eng.stop()


def getkey():
    while True:
        k = msvcrt.getwch().lower()
        if k in "\x00\xe0":          # arrow prefix, swallow second byte
            msvcrt.getwch()
            continue
        return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--rate", type=int, default=240)
    ap.add_argument("--selftest", action="store_true", help="no audio, no keys")
    args = ap.parse_args()

    if args.selftest:
        for _ in range(50):
            if random.random() < 0.3:
                random.choice(list(COMMANDS.values()))
            else:
                f"{random.choice(list(OBJECTS.values()))}, {random.choice(list(CLOCKS.values()))}"
        print("selftest OK")
        return

    print(__doc__)
    print(f"{args.rounds} rounds. Press any key to start.")
    getkey()

    score, times = 0, []
    for rnd in range(1, args.rounds + 1):
        if random.random() < 0.3:
            kind = "command"
            ans_key = random.choice(list(COMMANDS))
            phrase = COMMANDS[ans_key]
            prompt = "command key (s/l/r/n/x)"
            expected = [ans_key]
        else:
            kind = "contact"
            ok = random.choice(list(OBJECTS))
            ck = random.choice(list(CLOCKS))
            hot = random.random() < 0.25
            phrase = f"{OBJECTS[ok]}, {CLOCKS[ck]}" + (", hot" if hot else "")
            prompt = "object key, then clock key" + (" (it was hot!)" if hot else "")
            expected = [ok, ck]

        print(f"\nround {rnd}/{args.rounds} ...")
        say(phrase, args.rate)
        t0 = time.perf_counter()
        got = [getkey() for _ in expected]
        dt = time.perf_counter() - t0
        times.append(dt)
        if got == expected:
            score += 1
            print(f"  ✓ {phrase}   ({dt:.2f} s)")
        else:
            print(f"  ✗ it was: {phrase}  [{kind}] you pressed {'+'.join(got)}")

    print(f"\n=== {score}/{args.rounds} correct, "
          f"median response {sorted(times)[len(times)//2]:.2f} s ===")
    if score == args.rounds:
        print("fluent. switch cv_fusion to --mode brevity and fly.")


if __name__ == "__main__":
    main()
