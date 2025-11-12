#!/usr/bin/env python3
import argparse, os
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000

# ---------- utils ----------
def norm(x):
    m = np.max(np.abs(x)) + 1e-12
    return (x / m).astype(np.float32)

def load_wav(path):
    x, sr = sf.read(path, always_2d=False)
    if x.ndim > 1: x = x[:,0]
    if sr != SR:
        raise ValueError(f"Expected {SR} Hz; got {sr}. Resample first.")
    return x.astype(np.float32)

def save_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, norm(x), SR, subtype="PCM_24")

def guitarish_note(freq=220.0, dur=2.0):
    t = np.linspace(0, dur, int(SR*dur), endpoint=False)
    x = (np.sin(2*np.pi*freq*t)
         + 0.25*np.sin(2*np.pi*2*freq*t)
         + 0.15*np.sin(2*np.pi*3*freq*t))
    env = 1 - np.exp(-t*50)
    return norm(x * env * 0.6)

# ---------- building blocks ----------
def lp_pre_emphasis(x, fc=3500.0):
    rc = 1/(2*np.pi*fc); alpha = np.exp(-1/(SR*rc))
    y = np.copy(x)
    for n in range(1, len(y)):
        y[n] = alpha*y[n-1] + (1-alpha)*x[n]
    return y

def fuzz(x, drive=8.0, hard=0.45):
    y = lp_pre_emphasis(x, 3500)
    soft = np.tanh(drive*y)
    hardc = np.clip(drive*y, -0.6, 0.6)
    return norm((1-hard)*soft + hard*hardc)

def bandpass_sos(fc, q=2.5):
    bw = fc/q
    low = max(30.0, fc - bw/2.0)
    high = min(SR/2 - 100.0, fc + bw/2.0)
    return butter(2, [low/(SR/2), high/(SR/2)], btype='band', output='sos')

def wah_auto(x, f_lo=350, f_hi=2000, rate_hz=1.2, q=2.5):
    t = np.arange(len(x))/SR
    centers = f_lo + 0.5*(1+np.sin(2*np.pi*rate_hz*t))*(f_hi-f_lo)
    y = np.zeros_like(x)
    blk = 256
    for i in range(0, len(x), blk):
        sos = bandpass_sos(float(centers[i]), q=q)
        y[i:i+blk] = sosfilt(sos, x[i:i+blk])
    return norm(y)

def univibe(x, rate_hz=4.0, depth=0.9):
    t = np.arange(len(x))/SR
    lfo = 0.6 + 0.4*np.sin(2*np.pi*rate_hz*t)
    bases = np.array([220, 440, 700, 1100], dtype=float)
    y = x.copy()
    def allpass(seg, fc, d=0.9):
        w0 = 2*np.pi*fc/SR
        a = (1 - np.sin(w0))/(1 + np.sin(w0))
        out = np.zeros_like(seg); xm1=0.0; ym1=0.0
        for n in range(len(seg)):
            out[n] = -a*seg[n] + xm1 + a*ym1
            xm1 = seg[n]; ym1 = out[n]
        return (1-d)*seg + d*out
    blk = 128
    for base in bases:
        z = np.zeros_like(y)
        for i in range(0, len(y), blk):
            z[i:i+blk] = allpass(y[i:i+blk], float(base*(0.5 + lfo[i])), depth)
        y = z
    y *= (0.9*(1 + 0.15*np.sin(2*np.pi*(rate_hz/2.0)*t)))
    return norm(y)

def octavia(x):
    rect = np.abs(x)
    y = np.tanh(6*(rect - 0.1))
    return norm(y)

def leslie(x, rate_hz=5.5, dev_hz=3.0, am_depth=0.5):
    t = np.arange(len(x))/SR
    am = 1 + am_depth*np.sin(2*np.pi*rate_hz*t)
    fm = dev_hz*np.sin(2*np.pi*rate_hz*t)
    phase = 2*np.pi*np.cumsum(fm)/SR
    # crude FM around input: treat x's instantaneous phase as arctan(y/x) is overkill; use sine carrier
    fc = 330.0
    y = am * np.sin(2*np.pi*fc*t + phase)
    # Mix some original for realism
    y = 0.6*y + 0.4*x
    return norm(y)

def tape_echo(x, delay_ms=120, feedback=0.6, hf_loss=0.75):
    d = int(SR*delay_ms/1000.0)
    y = x.copy()
    buf = np.zeros_like(x)
    for n in range(d, len(x)):
        prev = hf_loss*buf[n-d]
        y[n] += feedback*prev
        buf[n] = y[n]
    return norm(y)

EFFECTS = {
    'fuzz':      lambda x: fuzz(x),
    'wah':       lambda x: wah_auto(x),
    'univibe':   lambda x: univibe(x),
    'octavia':   lambda x: octavia(x),
    'leslie':    lambda x: leslie(x),
    'tape':      lambda x: tape_echo(x),
}

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Hendrix-style audio chain")
    ap.add_argument('--in', dest='inp', help='48 kHz mono WAV input (dry). If omitted, synth note used.')
    ap.add_argument('--chain', nargs='+', default=['fuzz','wah','univibe','octavia','leslie','tape'],
                    help='Effect order (subset/permute any of: fuzz wah univibe octavia leslie tape)')
    ap.add_argument('--out', required=True, help='Final WAV output path')
    ap.add_argument('--stems', help='Folder to save intermediates (optional)')
    args = ap.parse_args()

    x = load_wav(args.inp) if args.inp else guitarish_note(220, 4.0)

    current = x
    if args.stems:
        os.makedirs(args.stems, exist_ok=True)
        save_wav(os.path.join(args.stems, "00_clean.wav"), current)

    for i, ef in enumerate(args.chain, start=1):
        if ef not in EFFECTS:
            raise ValueError(f"Unknown effect: {ef}")
        current = EFFECTS[ef](current)
        if args.stems:
            save_wav(os.path.join(args.stems, f"{i:02d}_{ef}.wav"), current)

    save_wav(args.out, current)

if __name__ == '__main__':
    main()

