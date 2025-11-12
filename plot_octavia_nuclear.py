import numpy as np
import matplotlib.pyplot as plt
import os

# ensure dirs
os.makedirs("out/data", exist_ok=True)
os.makedirs("out/figs", exist_ok=True)

# 1. make time axis
fs = 200_000          # high-ish sample rate so curves look smooth
duration = 0.020      # 20 ms, like before
t = np.linspace(0, duration, int(fs * duration), endpoint=False)
t_ms = t * 1000.0

# 2. guitar-ish sine
f = 440.0
vin = np.sin(2 * np.pi * f * t)

# 3. ideal full-wave rectified version
vrect = np.abs(vin)

# 4. simple Octavia-ish shaper
#    boost, subtract a little DC, clip
vout = 2.0 * vrect - 0.2
vout = np.clip(vout, -1.2, 1.2)

# 5. save data (optional but nice)
data = np.column_stack([t, vin, vrect, vout])
np.savetxt(
    "out/data/octavia_ideal.csv",
    data,
    delimiter=",",
    header="time_s,vin,vrect,vout",
    comments=""
)

# 6. plot, matching your other style
plt.figure(figsize=(6.4, 2.4))
plt.plot(t_ms, vin,   label="Input (440 Hz sine)", linewidth=1.0)
plt.plot(t_ms, vrect, label="Ideal full-wave (Octavia core)", linewidth=1.0)
plt.plot(t_ms, vout,  label="Shaped output", linewidth=1.2)

plt.title("Octavia – Idealized Rectifier/Clipper (Python)")
plt.xlabel("Time (ms)")
plt.ylabel("Voltage (V)")
plt.xlim(0, 20)
plt.ticklabel_format(style="plain", axis="y")
plt.legend(frameon=False, fontsize=7)
plt.tight_layout()
plt.savefig("out/figs/octavia_time.svg")
print("wrote out/figs/octavia_time.svg and out/data/octavia_ideal.csv")

