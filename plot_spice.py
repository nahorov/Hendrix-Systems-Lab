#!/usr/bin/env python3
"""
plot_spice.py — publication-ready SVGs from ngspice WRDATA/logs.

Subcommands
-----------
time-svg : plot time-domain traces from a WRDATA file
fft-svg  : plot magnitude FFT of one column from a WRDATA file
bode-svg : plot magnitude/phase from a WRDATA (re+im columns)
four-svg : plot bar chart of harmonics parsed from an ngspice log
"""

import argparse
import sys
import re
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

COMMENT_PREFIXES = ('*', ';', '.')

# ------------------------------ helpers ------------------------------

def _is_float(s: str) -> bool:
    try:
        float(s); return True
    except Exception:
        return False

def _clean_lines(path: Path):
    """
    Yield non-empty, non-comment lines. Keep potential headers like 'Index time ...'.
    """
    for raw in path.read_text(errors='ignore').splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith(COMMENT_PREFIXES):
            continue
        if s.lower().startswith(('no.', 'title', 'plotname', 'flags')):
            continue
        yield s

def _split(line: str):
    return re.split(r'\s+', line.strip())

def read_wrdata(path: str):
    """
    Parse a WRDATA ascii file. Returns (dict: col_name -> np.array, header_list).

    Robust to:
    - no header (assigns col0, col1, ...)
    - 'Index time v(out) ...' headers (drops the Index/No. column)
    - scientific notation in first data line (won't be misdetected as header)
    """
    p = Path(path)
    if not p.exists():
        sys.exit(f"ERROR: WRDATA not found: {p}")

    lines = list(_clean_lines(p))
    if not lines:
        sys.exit(f"ERROR: WRDATA {p} is empty or only comments.")

    # Decide header: it's a header iff at least one token is NOT a float.
    first_toks = _split(lines[0])
    header = None
    if any(not _is_float(tok) for tok in first_toks):
        header = first_toks
        rows = lines[1:]
    else:
        rows = lines

    # Parse data rows → numeric matrix
    data = []
    for line in rows:
        toks = _split(line)
        # skip fully non-numeric (rare)
        if not any(_is_float(t) for t in toks):
            continue
        try:
            vals = [float(t) for t in toks if _is_float(t)]
        except ValueError:
            continue
        if vals:
            data.append(vals)

    if not data:
        sys.exit(f"ERROR: No numeric rows found in WRDATA {p}.")

    arr = np.asarray(data, dtype=float)
    ncols = arr.shape[1]

    if header is None or len(header) != ncols:
        # Try to handle common 'Index time y1 y2 ...' with index in data too.
        # If header exists but length mismatch, prefer auto names.
        header = [f"col{i}" for i in range(ncols)]
    else:
        # Strip an initial index column if header says so and data width matches.
        if header and header[0].lower() in ('index', 'no.') and ncols == len(header):
            header = header[1:]
            arr = arr[:, 1:]
            ncols = arr.shape[1]

    dat = {name: arr[:, i] for i, name in enumerate(header)}
    return dat, header

def _save_svg(fig, outpath: str, tight=True):
    fig.tight_layout()
    fig.savefig(outpath, format='svg', bbox_inches='tight' if tight else None)
    plt.close(fig)

def _case_get(d: dict, key: str):
    if key in d: return key
    lk = key.lower()
    for k in d.keys():
        if k.lower() == lk: return k
    return None

# ------------------------------ plotters ------------------------------

def plot_time_svg(dat, xcol, ycols, title, outpath, ieee=False):
    # x: accept 'time' or fallback to col0 when absent
    kx = _case_get(dat, xcol)
    if kx is None and xcol.lower() == 'time' and 'col0' in dat:
        kx = 'col0'
    if kx is None:
        sys.exit(f"ERROR: x column '{xcol}' not found. Available: {list(dat.keys())}")

    x = dat[kx].astype(float)

    # Build list of (series_key, label). If named series not found and we have
    # unlabeled cols (col1..), map sequentially so charts still render.
    series = []
    missing = []
    for idx, yname in enumerate(ycols, start=1):
        ky = _case_get(dat, yname)
        if ky is not None:
            series.append((ky, yname))
        else:
            missing.append(yname)

    if series == []:
        # no named matches → try sequential mapping: col1, col2, ...
        seq = [f"col{i}" for i in range(1, 1+len(ycols))]
        have = [k for k in seq if k in dat]
        series = [(k, ycols[i]) for i, k in enumerate(have)]

    # Warn once if some names were missing
    if missing and series:
        print(f"NOTE: remapped unnamed time columns for {missing} -> {[s for _, s in series]}")

    fig = plt.figure(figsize=(3.25 if ieee else 8, 2.2 if ieee else 3))
    if title:
        plt.title(title)

    for ky, lbl in series:
        plt.plot(x, np.asarray(dat[ky], dtype=float), label=lbl)

    plt.xlabel(kx)
    plt.ylabel("Amplitude")
    if len(series) > 1:
        plt.legend()
    _save_svg(fig, outpath)


def plot_fft_svg(dat, ycol, sr, xlim, title, outpath, ieee=False):
    ky = _case_get(dat, ycol)
    if ky is None:
        sys.exit(f"ERROR: y column '{ycol}' not found. Available: {list(dat.keys())}")

    y = dat[ky].astype(float)
    N = len(y)
    if N < 4:
        sys.exit("ERROR: not enough samples for FFT.")
    N = min(65536, N - (N % 2))
    window = np.hanning(N)
    Y = np.fft.rfft(window * y[:N])
    f = np.fft.rfftfreq(N, 1.0 / sr)
    mag = 20 * np.log10(np.abs(Y) + 1e-12)

    fig = plt.figure(figsize=(3.25 if ieee else 8, 2.2 if ieee else 3))
    if title:
        plt.title(title)
    plt.plot(f, mag)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Magnitude (dBFS)")
    if xlim:
        plt.xlim(xlim)
    _save_svg(fig, outpath)

def plot_bode_svg(dat, fcol, yr_name, yi_name, title, out_mag, out_phase, ieee=False):
    def _k(d, name, alts=()):
        if name in d: return name
        lname = name.lower()
        for k in d:
            if k.lower() == lname: return k
        for a in alts:
            if a in d: return a
            for k in d:
                if k.lower() == a.lower(): return k
        return None

    kf = _k(dat, fcol, ('freq', 'frequency(Hz)', 'Frequency'))
    kr = _k(dat, yr_name)
    ki = _k(dat, yi_name)
    if kf is None or kr is None or ki is None:
        sys.exit(f"ERROR: missing columns. have={list(dat.keys())} want={(fcol, yr_name, yi_name)}")

    f  = np.asarray(dat[kf], float)
    re = np.asarray(dat[kr], float)
    im = np.asarray(dat[ki], float)

    # Keep only finite, strictly positive frequency rows
    mask = np.isfinite(f) & np.isfinite(re) & np.isfinite(im) & (f > 0)
    f, re, im = f[mask], re[mask], im[mask]

    if f.size == 0:
        print("WARNING: no positive/finite frequency rows to plot.")
        f = np.array([1.0, 10.0])
        re = np.array([0.0, 0.0])
        im = np.array([0.0, 0.0])

    H = re + 1j*im
    mag_db = 20*np.log10(np.maximum(np.abs(H), 1e-15))
    # Phase unwrap in degrees
    phase_deg = np.unwrap(np.angle(H)) * (180.0/np.pi)

    # Magnitude
    fig = plt.figure(figsize=(3.25 if ieee else 8, 2.2 if ieee else 3))
    if title: plt.title(title)
    plt.semilogx(f, mag_db)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Magnitude (dB)")
    _save_svg(fig, out_mag)

    # Phase
    fig = plt.figure(figsize=(3.25 if ieee else 8, 2.2 if ieee else 3))
    if title: plt.title(title.replace("Magnitude", "Phase"))
    plt.semilogx(f, phase_deg)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Phase (°)")
    _save_svg(fig, out_phase)


def parse_four_log(path, node=None):
    """
    Parse 'Fourier components of V(node) at frequency ...' blocks in an ngspice log.
    Returns {'freq': fundamental_hz_or_None, 'rows': [(n, mag_db, phase_deg, norm)]}
    """
    p = Path(path)
    if not p.exists():
        sys.exit(f"ERROR: log not found: {p}")
    txt = p.read_text(errors='ignore').splitlines()
    rows, fund, capture = [], None, False
    pat = re.compile(r'^\s*(\d+)\s+([-\d\.eE]+)\s+([-\d\.eE]+)\s+([-\d\.eE]+)')

    for line in txt:
        if 'Fourier components of' in line:
            if node and node.lower() not in line.lower():
                capture = False
                continue
            m = re.search(r'at frequency\s*([-\d\.eE]+)', line)
            if m:
                try:
                    fund = float(m.group(1))
                except Exception:
                    fund = None
            capture = True
            continue
        if capture:
            m = pat.match(line)
            if m:
                n = int(m.group(1))
                mag = float(m.group(2))
                db = float(m.group(3))
                ph = float(m.group(4))
                rows.append((n, db, ph, mag))
            elif line.strip() == '' and rows:
                break

    return {'freq': fund, 'rows': rows}

def plot_four_svg(parsed, title, outpath, limit=10, ieee=False):
    rows = parsed['rows'][:limit]
    harms = [r[0] for r in rows]
    mags = [r[1] for r in rows]  # dB column
    fig = plt.figure(figsize=(3.25 if ieee else 8, 2.2 if ieee else 3))
    if title:
        plt.title(title)
    plt.bar(harms, mags)
    plt.xlabel("Harmonic")
    plt.ylabel("Magnitude (dB)")
    _save_svg(fig, outpath)

# ------------------------------ CLI ------------------------------

def main():
    ap = argparse.ArgumentParser(description="Plot helpers for ngspice WRDATA/logs")
    sub = ap.add_subparsers(dest='cmd', required=True)

    # time-svg
    ap_t = sub.add_parser('time-svg', help='Plot time-domain traces from WRDATA')
    ap_t.add_argument('wrdata')
    ap_t.add_argument('--xcol', required=True)
    ap_t.add_argument('--ycols', nargs='+', required=True)
    ap_t.add_argument('--title')
    ap_t.add_argument('--out', required=True)
    ap_t.add_argument('--ieee', action='store_true', help='compact figure size for print')

    # fft-svg
    ap_f = sub.add_parser('fft-svg', help='Plot FFT magnitude from WRDATA')
    ap_f.add_argument('wrdata')
    ap_f.add_argument('--ycol', required=True)
    ap_f.add_argument('--sr', type=float, required=True, help='sample rate (Hz)')
    ap_f.add_argument('--xlim', nargs=2, type=float)
    ap_f.add_argument('--title')
    ap_f.add_argument('--out', required=True)
    ap_f.add_argument('--ieee', action='store_true')

    # bode-svg
    ap_b = sub.add_parser('bode-svg', help='Plot Bode magnitude & phase from WRDATA')
    ap_b.add_argument('wrdata')
    ap_b.add_argument('--fcol', required=True)
    ap_b.add_argument('--yr', required=True, help='column name for real part')
    ap_b.add_argument('--yi', required=True, help='column name for imag part')
    ap_b.add_argument('--title')
    ap_b.add_argument('--out', required=True, dest='out_mag', help='output SVG for magnitude')
    ap_b.add_argument('--phase-out', required=True, dest='out_phase', help='output SVG for phase')
    ap_b.add_argument('--ieee', action='store_true')

    # four-svg
    ap_4 = sub.add_parser('four-svg', help='Plot harmonics from an ngspice log')
    ap_4.add_argument('logfile')
    ap_4.add_argument('--node', help='filter on node name (e.g., v(out))')
    ap_4.add_argument('--title')
    ap_4.add_argument('--out', required=True)
    ap_4.add_argument('--limit', type=int, default=10)
    ap_4.add_argument('--ieee', action='store_true')

    args = ap.parse_args()

    if args.cmd == 'time-svg':
        dat, _ = read_wrdata(args.wrdata)
        plot_time_svg(dat, args.xcol, args.ycols, args.title, args.out, ieee=args.ieee)

    elif args.cmd == 'fft-svg':
        dat, _ = read_wrdata(args.wrdata)
        xlim = tuple(args.xlim) if args.xlim else None
        plot_fft_svg(dat, args.ycol, args.sr, xlim, args.title, args.out, ieee=args.ieee)

    elif args.cmd == 'bode-svg':
        dat, _ = read_wrdata(args.wrdata)
        plot_bode_svg(dat, args.fcol, args.yr, args.yi, args.title,
                      args.out_mag, args.out_phase, ieee=args.ieee)

    elif args.cmd == 'four-svg':
        parsed = parse_four_log(args.logfile, node=args.node)
        plot_four_svg(parsed, args.title, args.out, args.limit, ieee=args.ieee)

if __name__ == '__main__':
    main()

