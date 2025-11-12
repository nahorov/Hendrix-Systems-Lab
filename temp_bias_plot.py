#!/usr/bin/env python3
"""
temp_bias_plot.py — plot bias drift vs temperature from ngspice log (.op/.ac/.tran with .step temp)

Usage:
  python3 temp_bias_plot.py out/logs/ff_ge_temp.log \
      --out out/figs/ff_ge_temp.svg \
      --title "Fuzz Face (Ge/PNP) — Bias vs Temperature"
"""
import argparse, re, sys, numpy as np, matplotlib.pyplot as plt
from pathlib import Path

def parse_op_log(path):
    p = Path(path)
    if not p.exists():
        sys.exit(f"ERROR: log not found: {p}")
    text = p.read_text(errors="ignore").splitlines()
    temps, vc2, vb1, iin = [], [], [], []
    tpat = re.compile(r'Temperature\s*=\s*([-\d\.eE]+)')
    # Example matchers: adapt to how you echo nodes in your .control if needed
    c2pat = re.compile(r'v\(c2\)\s*=\s*([-\d\.eE]+)', re.I)
    b1pat = re.compile(r'v\(b1\)\s*=\s*([-\d\.eE]+)', re.I)
    inpat = re.compile(r'i\(vsig\)\s*=\s*([-\d\.eE]+)', re.I)

    cur_t = None; cur_c2 = None; cur_b1 = None; cur_i = None
    for line in text:
        m = tpat.search(line)
        if m:
            # push previous record if complete
            if cur_t is not None and None not in (cur_c2, cur_b1, cur_i):
                temps.append(cur_t); vc2.append(cur_c2); vb1.append(cur_b1); iin.append(cur_i)
            cur_t = float(m.group(1)); cur_c2 = cur_b1 = cur_i = None
            continue
        m = c2pat.search(line);  cur_c2 = float(m.group(1)) if m else cur_c2
        m = b1pat.search(line);  cur_b1 = float(m.group(1)) if m else cur_b1
        m = inpat.search(line);  cur_i  = float(m.group(1)) if m else cur_i

    if cur_t is not None and None not in (cur_c2, cur_b1, cur_i):
        temps.append(cur_t); vc2.append(cur_c2); vb1.append(cur_b1); iin.append(cur_i)

    if not temps:
        sys.exit("ERROR: no temperature blocks parsed from log. Check .control echo or node names.")
    return np.asarray(temps), np.asarray(vc2), np.asarray(vb1), np.asarray(iin)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('logfile')
    ap.add_argument('--out', required=True)
    ap.add_argument('--title')
    args = ap.parse_args()

    t, vc2, vb1, iin = parse_op_log(args.logfile)

    plt.figure(figsize=(8,3))
    if args.title: plt.title(args.title)
    plt.plot(t, vc2, 'o-', label='V(C2)')
    plt.plot(t, vb1, 's--', label='V(B1)')
    plt.xlabel("Temperature (°C)"); plt.ylabel("Voltage (V)")
    plt.legend()
    plt.tight_layout(); plt.savefig(args.out, format='svg', bbox_inches='tight')

if __name__ == "__main__":
    main()

