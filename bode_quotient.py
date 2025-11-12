#!/usr/bin/env python3
"""
bode_quotient.py
Compute H(f) = A(f) / B(f) from ngspice WRDATA and plot magnitude/phase.
Robust to duplicate 'frequency' columns and non-positive/NaN rows.
"""

import sys, argparse, math
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

def read_wrdata(p: Path):
    """Read ngspice WRDATA (ascii) into dict of column_name -> np.array."""
    text = p.read_text(errors='ignore').strip().splitlines()
    if not text:
        raise ValueError(f"empty WRDATA: {p}")
    # try header:
    hdr = text[0].split()
    # If header looks like numeric first token, synthesize names
    def _isnum(s):
        try: float(s); return True
        except: return False
    if _isnum(hdr[0]):
        # synthesize col0, col1, ...
        names = [f"col{i}" for i in range(len(hdr))]
        rows  = [list(map(float, line.split())) for line in text]
    else:
        names = hdr
        rows  = []
        for line in text[1:]:
            if not line.strip(): continue
            parts = line.split()
            # pad/trim to header length
            if len(parts) < len(names):
                parts += ['nan']*(len(names)-len(parts))
            elif len(parts) > len(names):
                parts = parts[:len(names)]
            rows.append([float(x) if x not in ('nan','NaN') else float('nan') for x in parts])

    arr = np.array(rows, dtype=float)
    cols = {}
    # handle duplicate header tokens by suffixing _# and also keep first occurrence plain
    seen = {}
    for j, nm in enumerate(names):
        nm_clean = nm.strip()
        if nm_clean in seen:
            k = seen[nm_clean] + 1
            seen[nm_clean] = k
            nm_key = f"{nm_clean}_{k}"
        else:
            seen[nm_clean] = 0
            nm_key = nm_clean
        cols[nm_key] = arr[:, j]
        # Also store the first occurrence under the bare name
        if seen[nm_clean] == 0:
            cols[nm_clean] = arr[:, j]
    return cols

def pick_frequency(cols: dict, prefer=("frequency","freq","Frequency","frequency_1","frequency_2")):
    """Choose a frequency column that has finite, strictly positive values."""
    candidates = [k for k in cols.keys() if k.lower().startswith("frequency") or k.lower()=="freq"]
    # preserve preference order
    ordered = list(prefer) + [k for k in candidates if k not in prefer]
    for k in ordered:
        if k in cols:
            f = np.asarray(cols[k], float)
            if np.isfinite(f).any() and (f > 0).any():
                return k
    # fallback: any column with positive values
    for k, v in cols.items():
        v = np.asarray(v, float)
        if np.isfinite(v).any() and (v > 0).any():
            return k
    raise KeyError("no suitable positive frequency column found")

def getcol(cols, name, alts=()):
    """Fetch column by exact name or case-insensitive match; try alternatives."""
    keys = list(cols.keys())
    if name in cols: return cols[name]
    lname = name.lower()
    for k in keys:
        if k.lower() == lname: return cols[k]
    for a in alts:
        if a in cols: return cols[a]
        for k in keys:
            if k.lower() == a.lower(): return cols[k]
    raise KeyError(f"column not found: {name}")

def cmplx(re, im):
    return np.asarray(re, float) + 1j*np.asarray(im, float)

def save_svg(fig, path):
    fig.tight_layout()
    fig.savefig(path, format="svg")
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wrdata", help="input WRDATA file")
    ap.add_argument("--fcol", default="frequency")
    ap.add_argument("--an", required=True, help="A real column name")
    ap.add_argument("--ai", required=True, help="A imag column name")
    ap.add_argument("--bn", required=True, help="B real column name")
    ap.add_argument("--bi", required=True, help="B imag column name")
    ap.add_argument("--title", default="Bode Quotient")
    ap.add_argument("--out-mag", required=True)
    ap.add_argument("--out-phase", required=True)
    ap.add_argument("--ieee", action="store_true")
    args = ap.parse_args()

    p = Path(args.wrdata)
    cols = read_wrdata(p)

    # pick a good frequency column (handles duplicates/zeros)
    try:
        kf = pick_frequency(cols, prefer=(args.fcol, "frequency", "freq", "frequency_1", "frequency_2"))
    except Exception as e:
        sys.exit(f"ERROR: {e}. Available={list(cols.keys())}")

    # get vectors (allow a few aliases just in case)
    Ar = getcol(cols, args.an, ("re:real(v(in))","real(v(in))","re(v(in))","col3"))
    Ai = getcol(cols, args.ai, ("im:imag(v(in))","imag(v(in))","im(v(in))","col4"))
    Br = getcol(cols, args.bn, ("real(i(vsig))","re(i(vsig))","real(@vsig[i])","re(@vsig[i])","col5","col7"))
    Bi = getcol(cols, args.bi, ("imag(i(vsig))","im(i(vsig))","imag(@vsig[i])","im(@vsig[i])","col6","col8"))

    f  = np.asarray(cols[kf], float)
    Ar = np.asarray(Ar, float)
    Ai = np.asarray(Ai, float)
    Br = np.asarray(Br, float)
    Bi = np.asarray(Bi, float)

    # mask invalid rows
    m = np.isfinite(f) & np.isfinite(Ar) & np.isfinite(Ai) & np.isfinite(Br) & np.isfinite(Bi) & (f > 0)
    f, Ar, Ai, Br, Bi = f[m], Ar[m], Ai[m], Br[m], Bi[m]

    if f.size == 0:
        print("WARNING: no positive/finite rows; synthesizing tiny placeholder.")
        f = np.array([1.0, 10.0])
        Ar = Ai = Br = Bi = np.zeros_like(f)

    A = cmplx(Ar, Ai)
    B = cmplx(Br, Bi)
    # avoid divide-by-zero
    H = A / np.where(np.abs(B) > 1e-30, B, 1e-30)

    mag = 20*np.log10(np.maximum(np.abs(H), 1e-15))
    ph  = np.unwrap(np.angle(H)) * (180/np.pi)

    fig = plt.figure(figsize=(3.25 if args.ieee else 8, 2.2 if args.ieee else 3))
    if args.title: plt.title(args.title)
    plt.semilogx(f, mag)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Magnitude (dB)")
    save_svg(fig, args.out_mag)

    fig = plt.figure(figsize=(3.25 if args.ieee else 8, 2.2 if args.ieee else 3))
    if args.title: plt.title(args.title.replace("Magnitude", "Phase"))
    plt.semilogx(f, ph)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Phase (°)")
    save_svg(fig, args.out_phase)

if __name__ == "__main__":
    main()

