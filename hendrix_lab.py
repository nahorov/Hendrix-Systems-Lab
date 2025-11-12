#!/usr/bin/env python3
import os, argparse
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from scipy.signal import butter, sosfilt

SR = 48000  # sample rate

# ---------- utils ----------
def ensure_dir(d): os.makedirs(d, exist_ok=True)
def norm(x): return x / (np.max(np.abs(x)) + 1e-12)

def save_audio(path, x):
    x = norm(x).astype(np.float32)
    sf.write(path, x, SR, subtype="PCM_24")

def save_plot_time(path, x, ms=40, title=""):
    n = int(SR * (ms/1000.0))
    t = np.arange(n)/SR*1000.0
    plt.figure(figsize=(8,3))
    if title: plt.title(title)
    plt.plot(t, x[:n])
    plt.xlabel("Time (ms)"); plt.ylabel("Amplitude")
    plt.tight_layout()
    plt.savefig(path); plt.close()

def save_plot_fft(path, x, title=""):
    N = 4096
    X = np.fft.rfft(np.hanning(N)*x[:N])
    f = np.fft.rfftfreq(N, 1/SR)
    mag = 20*np.log10(np.abs(X)+1e-12)
    plt.figure(figsize=(8,3))
    if title: plt.title(title)
    plt.plot(f, mag)
    plt.xlabel("Frequency (Hz)"); plt.ylabel("Magnitude (dBFS)")
    plt.xlim(0, 6000)
    plt.tight_layout()
    plt.savefig(path); plt.close()

def save_plot_spec(path, x, title=""):
    plt.figure(figsize=(8,3))
    if title: plt.title(title)
    plt.specgram(x, NFFT=1024, Fs=SR, noverlap=768)
    plt.xlabel("Time (s)"); plt.ylabel("Frequency (Hz)")
    plt.tight_layout()
    plt.savefig(path); plt.close()

# ---------- sources ----------
def guitarish_note(freq=220.0, dur=2.0):
    t = np.linspace(0, dur, int(SR*dur), endpoint=False)
    x = (np.sin(2*np.pi*freq*t)
         + 0.25*np.sin(2*np.pi*2*freq*t)
         + 0.15*np.sin(2*np.pi*3*freq*t))
    env = 1 - np.exp(-t*50)  # pick attack
    return norm(x * env * 0.6)

# ---------- effects ----------
def compressor_soft(x, drive_db=12, knee="soft"):
    g = 10**(drive_db/20)
    y = g*x
    if knee == "soft":
        y = np.tanh(y)  # smooth saturation as poor-man’s soft knee
    return norm(y)

def hard_clip(x, th=0.6):
    return norm(np.clip(x, -th, th))

def fuzz_face_like(x):
    # crude model: pickup/cable low-pass then mixed soft/hard clip
    fc = 3500.0
    rc = 1/(2*np.pi*fc)
    alpha = np.exp(-1/(SR*rc))
    y = np.copy(x)
    for n in range(1, len(y)):
        y[n] = alpha*y[n-1] + (1-alpha)*x[n]
    gain = 8.0
    soft = np.tanh(gain*y)
    hard = np.clip(gain*y, -0.6, 0.6)
    return norm(0.55*soft + 0.45*hard)

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
        sos = bandpass_sos(centers[i], q=q)
        y[i:i+blk] = sosfilt(sos, x[i:i+blk])
    return norm(y)

def univibe(x, rate_hz=4.0, depth=0.9):
    # 4-stage 1st-order all-pass w/ LFO; dry+wet mix
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
            fc = base * (0.5 + lfo[i])
            z[i:i+blk] = allpass(y[i:i+blk], fc, depth)
        y = z
    # slight AM "throb"
    y *= (0.9*(1 + 0.15*np.sin(2*np.pi*(rate_hz/2.0)*t)))
    return norm(y)

def octavia(x):
    # octave-up via full-wave rectification, then fuzz
    rect = np.abs(x)
    y = np.tanh(6*(rect - 0.1))
    return norm(y)

def leslie(x, rate_hz=5.5, dev_hz=3.0, am_depth=0.5):
    t = np.arange(len(x))/SR
    am = 1 + am_depth*np.sin(2*np.pi*rate_hz*t)
    fm = dev_hz*np.sin(2*np.pi*rate_hz*t)
    phase = 2*np.pi*np.cumsum((fm)/SR)
    # apply FM by phase modulation around the original carrier content
    y = am * np.sin(np.unwrap(np.angle(np.fft.ifft(np.fft.fft(x)))) + phase)
    # The above is a crude trick; for musical signals, just modulate a sine carrier:
    # y = am * np.sin(phase0 + 2*pi*fc*t + phase)
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

def bitcrush(x, bits=8, downsample=3):
    q = 2**bits
    y = np.round(x*(q/2-1))/(q/2-1)
    return norm(y[::downsample])

# ---------- pipeline ----------
def process(input_wav=None, outdir="out"):
    ensure_dir(outdir)
    # source audio
    if input_wav and os.path.isfile(input_wav):
        x, sr = sf.read(input_wav, always_2d=False)
        assert sr == SR, f"Resample to {SR} Hz first (got {sr})"
        x = norm(x.astype(float))
    else:
        x = guitarish_note(220, 2.0)

    # save clean
    save_audio(f"{outdir}/00_clean.wav", x)
    save_plot_time(f"{outdir}/00_clean_time.svg", x, title="Clean")
    save_plot_fft(f"{outdir}/00_clean_fft.svg", x, title="Clean (FFT)")

    # compressor
    c = compressor_soft(x, drive_db=12)
    save_audio(f"{outdir}/01_compressor.wav", c)
    save_plot_time(f"{outdir}/01_compressor_time.svg", c, title="Compressor (soft knee)")
    save_plot_fft(f"{outdir}/01_compressor_fft.svg", c, title="Compressor (FFT)")

    # fuzz face-esque
    fz = fuzz_face_like(x)
    save_audio(f"{outdir}/02_fuzz.wav", fz)
    save_plot_time(f"{outdir}/02_fuzz_time.svg", fz, title="Fuzz Face-style")
    save_plot_fft(f"{outdir}/02_fuzz_fft.svg", fz, title="Fuzz Face-style (FFT)")

    # hard clip (truncation)
    hc = hard_clip(x, th=0.6)
    save_audio(f"{outdir}/03_hardclip.wav", hc)
    save_plot_time(f"{outdir}/03_hardclip_time.svg", hc, title="Hard clipping")
    save_plot_fft(f"{outdir}/03_hardclip_fft.svg", hc, title="Hard clipping (FFT)")

    # wah (auto sweep) + spectrogram
    wh = wah_auto(x, f_lo=350, f_hi=2000, rate_hz=1.2)
    save_audio(f"{outdir}/04_wah.wav", wh)
    save_plot_time(f"{outdir}/04_wah_time.svg", wh, title="Wah (auto sweep)")
    save_plot_spec(f"{outdir}/04_wah_spec.svg", wh, title="Wah (spectrogram)")

    # uni-vibe
    uv = univibe(x, rate_hz=4.0)
    save_audio(f"{outdir}/05_univibe.wav", uv)
    save_plot_time(f"{outdir}/05_univibe_time.svg", uv, title="Uni-Vibe (phase wobble)")
    save_plot_fft(f"{outdir}/05_univibe_fft.svg", uv, title="Uni-Vibe (FFT)")

    # octavia
    oc = octavia(x)
    save_audio(f"{outdir}/06_octavia.wav", oc)
    save_plot_time(f"{outdir}/06_octavia_time.svg", oc, title="Octavia (full-wave)")
    save_plot_fft(f"{outdir}/06_octavia_fft.svg", oc, title="Octavia (FFT)")

    # leslie
    ls = leslie(x, rate_hz=5.5, dev_hz=3.0, am_depth=0.5)
    save_audio(f"{outdir}/07_leslie.wav", ls)
    save_plot_time(f"{outdir}/07_leslie_time.svg", ls, title="Leslie (AM+FM)")
    save_plot_fft(f"{outdir}/07_leslie_fft.svg", ls, title="Leslie (FFT)")

    # tape echo
    te = tape_echo(x, delay_ms=120, feedback=0.6, hf_loss=0.75)
    save_audio(f"{outdir}/08_tape_echo.wav", te)
    save_plot_time(f"{outdir}/08_tape_echo_time.svg", te, title="Tape echo")
    save_plot_fft(f"{outdir}/08_tape_echo_fft.svg", te, title="Tape echo (FFT)")

    # bitcrush (as “truncation” example)
    bc = bitcrush(x, bits=8, downsample=2)
    save_audio(f"{outdir}/09_bitcrush.wav", bc)
    # time/fft on resampled length
    save_plot_time(f"{outdir}/09_bitcrush_time.svg", bc, title="Bitcrush/Downsample")
    save_plot_fft(f"{outdir}/09_bitcrush_fft.svg", bc, title="Bitcrush/Downsample (FFT)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", help="optional input WAV @48kHz mono (e.g., your LMMS export)")
    ap.add_argument("--outdir", default="out")
    args = ap.parse_args()
    process(args.inp, args.outdir)

