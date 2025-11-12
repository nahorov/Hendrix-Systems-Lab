#!/usr/bin/env python3
"""
merge_bode.py — overlay multiple Bode curves (mag + phase) from WRDATA files.

Each input is given as PATH[:LABEL]
If LABEL is omitted, the filename stem is used.

Example:
  python3 merge_bode.py \
    --out-mag out/figs/vibe_positions_mag.svg \
    --out-phase out/figs/vibe_positions_phase.svg \
    --title "Uni-Vibe — Magnitude" \
    --fcol frequency --recol "real(v(out))" --imcol "imag(v(out))" \
    out/data/vibe_R6k.dat:"6k" \
    out/data/vibe_R12k.dat:"12k" \
    out/data/vibe_R22k.dat:"22k" \
    out/data/vibe_R33k.dat:"33k" \
    out/data/vibe_R47k.dat:"47k" \
    out/data/vibe_R68k.dat:"68k"
"""

import argparse
import sys
import re
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

COMMENT_PREFIXES = ('*', ';', '.')

def _is_float(s: str) -> bool:
    try:
        float(s); return True
    except Exception:
        return False

def _clean_lines(path: Path):
    for raw in path.read_text(errors='ignore').splitlines():
        s = raw.strip()
        if not s: continue
        if s.startswith(COMMENT_PREFIXES): continue
        if s.lower().startswith(('index','no.','title','plotname','flags')): continue
        yield s

def read_wrdata(path: Path):
    if not path.exists():
        sys.exit(f"ERROR: WRDATA not found: {path}")
    lines = list(_clean_lines(path))
    if not lines:
        sys.exit(f"ERROR: WRDATA {path} is empty.")
    header = None
    if re.search(r'[A-Za-z]', lines[0]):
        header = re.split(r'\s+', lines[0].strip())
        rows = lines[1:]
    else:
        rows = lines
    data = []
    for line in rows:
        toks = re.split(r'\s+', line.strip())
        try:
            vals = [float(tok) for tok in toks]
        except ValueError:
            continue
        if vals:
            data.append(vals)
    if not data:
        sys.exit(f"ERROR: no numeric rows in {path}")
    arr = np.asarray(data, dtype=float)
    if not header or len(header) != arr.shape[1]:
        header = [f"col{i}" for i in range(arr.shape[1])]
    return {name: arr[:, i] for i, name in enumerate(header)}

def grab(cols, name, fallbacks=()):
    if name in cols:
        return cols[name].astype(float)
    for n in fallbacks:
        if n in cols: return cols[n].astype(float)
    # try case-insensitive match
    for k in cols.keys():
        if k.lower() == name.lower():
            return cols[k].astype(float)
    raise KeyError(name)

def add_curve(ax_mag, ax_phase, cols, label, fcol, recol, imcol):
    f   = grab(cols, fcol, ('Frequency','freq','f'))
    re_ = grab(cols, recol, ('re:re','real(v(out))','re','real'))
    im_ = grab(cols, imcol, ('im:im','imag(v(out))','im','imag'))

    order = np.argsort(f)
    f, re_, im_ = f[order], re_[order], im_[order]
    mag = 20*np.log10(np.hypot(re_, im_) + 1e-24)
    ph  = np.degrees(np.arctan2(im_, re_))

    ax_mag.semilogx(f, mag, label=label)
    ax_phase.semilogx(f, ph,  label=label)

def save_svg(fig, outpath):
    fig.tight_layout()
    fig.savefig(outpath, format='svg', bbox_inches='tight')
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser(description="Overlay Bode curves from multiple WRDATA files.")
    ap.add_argument('--out-mag', required=True, help='output SVG for magnitude')
    ap.add_argument('--out-phase', required=True, help='output SVG for phase')
    ap.add_argument('--title', default='')
    ap.add_argument('--fcol', default='frequency')
    ap.add_argument('--recol', default='real(v(out))')
    ap.add_argument('--imcol', default='imag(v(out))')
    ap.add_argument('inputs', nargs='+', help='PATH[:LABEL] ...')
    ap.add_argument('--ieee', action='store_true', help='compact figure size for print')
    args = ap.parse_args()

    if not args.inputs:
        sys.exit("No inputs provided")

    mag_fig = plt.figure(figsize=(3.25 if args.ieee else 8, 2.2 if args.ieee else 3))
    if args.title:
        plt.title(args.title)
    ax_mag = plt.gca()

    phase_fig = plt.figure(figsize=(3.25 if args.ieee else 8, 2.2 if args.ieee else 3))
    if args.title:
        plt.title(args.title.replace("Magnitude", "Phase"))
    ax_phase = plt.gca()

    for spec in args.inputs:
        p, _, label = spec.partition(':')
        path = Path(p)
        if not label:
            label = path.stem
        cols = read_wrdata(path)
        add_curve(ax_mag, ax_phase, cols, label, args.fcol, args.recol, args.imcol)

    ax_mag.set_xlabel("Frequency (Hz)");   ax_mag.set_ylabel("Magnitude (dB)")
    ax_phase.set_xlabel("Frequency (Hz)"); ax_phase.set_ylabel("Phase (degrees)")
    ax_mag.legend(); ax_phase.legend()

    save_svg(mag_fig, args.out_mag)
    save_svg(phase_fig, args.out_phase)

if __name__ == "__main__":
    main()

