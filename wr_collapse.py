#!/usr/bin/env python3
"""
wr_collapse.py — normalize ngspice WRDATA into 3 columns:
    frequency  re  im

Usage:
  python3 wr_collapse.py in_wrdata.dat out_wrdata_clean.dat
"""

import sys, re
from pathlib import Path

COMMENT_PREFIXES = ('*', ';', '.')

def is_float(s):
    try:
        float(s); return True
    except Exception:
        return False

def load_rows(path: Path):
    for raw in path.read_text(errors="ignore").splitlines():
        s = raw.strip()
        if not s: continue
        if s.startswith(COMMENT_PREFIXES): continue
        if s.lower().startswith(('index','no.','title','plotname','flags')): continue
        yield s

def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: wr_collapse.py IN.dat OUT.dat")

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    if not src.exists():
        sys.exit(f"ERROR: input WRDATA not found: {src}")

    lines = list(load_rows(src))
    if not lines:
        sys.exit(f"ERROR: input WRDATA {src} is empty.")

    header = None
    # header if first non-empty line has any alpha chars
    if re.search(r'[A-Za-z]', lines[0]):
        header = re.split(r'\s+', lines[0].strip())
        rows = lines[1:]
    else:
        rows = lines

    data = []
    for line in rows:
        toks = re.split(r'\s+', line.strip())
        nums = [float(t) for t in toks if is_float(t)]
        if nums:
            data.append(nums)

    if not data:
        sys.exit(f"ERROR: no numeric rows found in {src}")

    # If we have a header, try to map columns by name; else, take first 3 numbers.
    f_idx = r_idx = i_idx = None
    if header:
        lname = [h.lower() for h in header]
        # candidate lists
        f_cands = ['frequency', 'freq', 'f']
        r_cands = ['real(v(out))', 're:re', 're', 'real']
        i_cands = ['imag(v(out))', 'im:im', 'im', 'imag']
        for idx, h in enumerate(lname):
            if f_idx is None and any(c == h for c in f_cands): f_idx = idx
            if r_idx is None and any(c == h for c in r_cands): r_idx = idx
            if i_idx is None and any(c == h for c in i_cands): i_idx = idx

    out_lines = ["frequency re im"]
    if f_idx is not None and r_idx is not None and i_idx is not None:
        for row in data:
            # guard for ragged rows
            if max(f_idx, r_idx, i_idx) >= len(row): continue
            out_lines.append(f"{row[f_idx]} {row[r_idx]} {row[i_idx]}")
    else:
        # fallback: use first three numbers in each row
        for row in data:
            if len(row) < 3: continue
            out_lines.append(f"{row[0]} {row[1]} {row[2]}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out_lines))
    print(f"Wrote {dst} ({len(out_lines)-1} rows)")

if __name__ == "__main__":
    main()

