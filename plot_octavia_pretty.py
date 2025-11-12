import numpy as np
import matplotlib.pyplot as plt

data = np.loadtxt("out/data/octavia.dat")

t_ms = data[:, 0] * 1000.0
vin  = data[:, 1]
vrect= data[:, 2]
vout = data[:, 3]

plt.figure(figsize=(6.4, 2.4))
plt.plot(t_ms, vin,   label="Input (440 Hz sine)", linewidth=1.0)
plt.plot(t_ms, vrect, label="Rectified node (bridge)", linewidth=1.0)
plt.plot(t_ms, vout,  label="Post-shaper output", linewidth=1.2)

plt.title("Octavia – Input vs. Rectified Output (SPICE)")
plt.xlabel("Time (ms)")
plt.ylabel("Voltage (V)")
plt.xlim(0, 20)
plt.ticklabel_format(style="plain", axis="y")
plt.legend(frameon=False, fontsize=7)
plt.tight_layout()
plt.savefig("out/figs/octavia_time.svg")
