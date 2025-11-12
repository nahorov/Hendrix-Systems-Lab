#!/usr/bin/env python3
import argparse, re, csv, sys
import numpy as np
from pathlib import Path

COMMENT_PREFIXES = ('*', ';', '.')

def _clean_lines(path: Path):
    if not path.exists():
        sys.exit(f"ERROR: WRDATA not found: {path}")
    lines = []
    for raw in path.read_text(errors='ignore').splitlines():
        s = raw.strip()
        if not s: continue
        if s.startswith(COMMENT_PREFIXES): continue
        if s.lower().startswith(('index','no.','title','plotname','flags')): continue
        lines.append(s)
    if not lines:
        sys.exit(f"ERROR: WRDATA {path} is empty.")
    return lines

def read_wrdata(path):
    lines = _clean_lines(Path(path))
    header = None
    if re.search(r'[A-Za-z]', lines[0]):
        header = re.split(r'\s+', lines[0].strip())
        rows = lines[1:]
    else:
        rows = lines
    data = []
    for line in rows:
        toks = re.split(r'\s+', line)
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

def db(v):
    return 20*np.log10(np.maximum(v, 1e-24))

def find_band_edges(f, mag_db, peak_idx):
    peak_mag = mag_db[peak_idx]
    target = peak_mag - 3.0
    # Search left
    lo_idx = peak_idx
    while lo_idx > 0 and mag_db[lo_idx] > target:
        lo_idx -= 1
    # linear interp
    if lo_idx < peak_idx:
        x0,x1 = f[lo_idx], f[lo_idx+1]
        y0,y1 = mag_db[lo_idx], mag_db[lo_idx+1]
        flo = x0 + (target - y0) * (x1 - x0) / (y1 - y0 + 1e-24)
    else:
        flo = f[0]
    # Search right
    hi_idx = peak_idx
    while hi_idx < len(f)-1 and mag_db[hi_idx] > target:
        hi_idx += 1
    if hi_idx > peak_idx:
        x0,x1 = f[hi_idx-1], f[hi_idx]
        y0,y1 = mag_db[hi_idx-1], mag_db[hi_idx]
        fhi = x0 + (target - y0) * (x1 - x0) / (y1 - y0 + 1e-24)
    else:
        fhi = f[-1]
    bw = max(fhi - flo, 1e-9)
    f0 = f[peak_idx]
    Q = f0 / bw
    return f0, flo, fhi, bw, Q

def f0_bw_q(f, mag_db):
    peak_idx = int(np.argmax(mag_db))
    return find_band_edges(f, mag_db, peak_idx)

def main():
    ap = argparse.ArgumentParser(description="Compute wah resonant f0/BW/Q across positions.")
    ap.add_argument('inputs', nargs='+', help='WRDATA files, each one curve (one position)')
    ap.add_argument('--labels', nargs='*', help='optional labels matching inputs (e.g., positions)')
    ap.add_argument('--fcol', default='frequency')
    ap.add_argument('--recol', default='real(v(out))')
    ap.add_argument('--imcol', default='imag(v(out))')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    labels = args.labels or [Path(p).stem for p in args.inputs]
    if len(labels) != len(args.inputs):
        sys.exit("ERROR: number of labels must match number of inputs.")

    rows = []
    for pos, path in zip(labels, args.inputs):
        cols = read_wrdata(path)
        # tolerate variants
        f = (cols.get(args.fcol) or cols.get('Frequency') or cols.get('freq'))
        if f is None:
            sys.exit(f"ERROR: cannot find frequency column in {path}")
        re_ = (cols.get(args.recol) or cols.get('re:re') or cols.get('real(v(out))') or cols.get('re'))
        im_ = (cols.get(args.imcol) or cols.get('im:im') or cols.get('imag(v(out))') or cols.get('im'))
        if re_ is None or im_ is None:
            sys.exit(f"ERROR: cannot find complex columns in {path}")
        f = f.astype(float)
        mag = np.hypot(re_.astype(float), im_.astype(float))
        mag_db = db(mag)
        # ensure monotonic f for edge-finding
        order = np.argsort(f); f = f[order]; mag_db = mag_db[order]
        f0, flo, fhi, bw, Q = f0_bw_q(f, mag_db)
        rows.append((float(pos) if re.fullmatch(r'[-+]?\d*\.?\d+', str(pos)) else pos, f0, flo, fhi, bw, Q))

    # Sort numeric labels if possible; keep original order otherwise
    try:
        rows.sort(key=lambda r: float(r[0]))
    except Exception:
        pass

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['position','f0_hz','flo_-3dB_hz','fhi_-3dB_hz','bw_hz','Q'])
        for r in rows:
            w.writerow([r[0], f'{r[1]:.2f}', f'{r[2]:.2f}', f'{r[3]:.2f}', f'{r[4]:.2f}', f'{r[5]:.2f}'])

if __name__ == '__main__':
    main()

