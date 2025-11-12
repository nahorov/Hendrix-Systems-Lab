#!/usr/bin/env python3
import argparse, numpy as np, matplotlib.pyplot as plt

SR=48000

def tape_echo(x, delay_ms=120, feedback=0.6, hf_loss=0.75):
    d = int(SR*delay_ms/1000.0)
    y = x.copy()
    buf = np.zeros_like(x)
    for n in range(d, len(x)):
        prev = hf_loss*buf[n-d]
        y[n] += feedback*prev
        buf[n] = y[n]
    return y

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--delay', type=float, default=120)
    ap.add_argument('--feedback', type=float, default=0.6)
    ap.add_argument('--hf', type=float, default=0.75)
    ap.add_argument('--dur', type=float, default=1.2)
    ap.add_argument('--out', required=True)
    args=ap.parse_args()

    N=int(SR*args.dur)
    x=np.zeros(N); x[0]=1.0  # unit impulse
    y=tape_echo(x, args.delay, args.feedback, args.hf)

    t=np.arange(min(N, int(SR*args.dur)))/SR
    plt.figure(figsize=(8,3))
    plt.title(f"Tape Echo Impulse Response (delay {args.delay} ms, fb {args.feedback}, HF {args.hf})")
    plt.plot(t, y[:len(t)])
    plt.xlabel("Time (s)"); plt.ylabel("Amplitude")
    plt.tight_layout(); plt.savefig(args.out, format='svg', bbox_inches='tight')

if __name__=='__main__':
    main()

