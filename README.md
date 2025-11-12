# Hendrix Systems Lab — Rebuilding a Guitar Hero’s Signal Chain (2025)

This repository contains the Python, ngspice, and Makefile sources used to
generate all figures and data for the article  
**“Hendrix, Systems Engineer: Rebuilding a Guitar Hero’s Signal Chain with SPICE”**  
(submitted to *IEEE Spectrum*, 2025).

It reconstructs the analog signal path used by **Jimi Hendrix (1966–1970)**
as a cascade of nonlinear stages—Fuzz Face, Octavia, Wah, Uni-Vibe, and Marshall stack—
and models them as analog systems using **ngspice** and **Python** tools
for visualization and audio demonstration.

All SVG figures appearing in the manuscript and supplementary ODT files were
generated directly from these scripts with no manual edits.

---

## 🔧 Environment

| Tool | Version tested |
|------|----------------|
| Python | 3.11 |
| ngspice | 42.1 |
| NumPy | ≥ 1.26 |
| SciPy | ≥ 1.13 |
| Matplotlib | ≥ 3.8 |
| soundfile | ≥ 0.12 |

Install the Python stack with:

```bash
pip install -r requirements.txt
````

(`requirements.txt` should list the packages above with pinned versions.)

---

## 📁 Contents

| File                                                                                                                      | Purpose                                                                                               |
| ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Makefile**                                                                                                              | Automates ngspice runs and SVG generation. Main entry point.                                          |
| **fuzzface_ge_pnp_posgnd.cir**, **fuzzface_si.cir**                                                                       | Germanium and silicon Fuzz Face transistor models.                                                    |
| **octavia_behavioral.cir**, **octavia_transformer_rect.cir**                                                              | Two Octavia variants (behavioral and transformer/rectifier).                                          |
| **vox_wah_param.cir**                                                                                                     | VOX V847 wah-wah parameterized deck.                                                                  |
| **univibe_frozen_lfo.cir**, **univibe_frozen_lfo_sweep.cir**                                                              | Uni-Vibe phase-shift network (fixed and swept LFO).                                                   |
| **bode_quotient.py**, **merge_bode.py**, **plot_spice.py**, **wr_collapse.py**, **wah_q_table.py**, **temp_bias_plot.py** | Python utilities for parsing WRDATA logs and producing Bode, phase, and Q-factor plots.               |
| **chain_hendrix.py**, **hendrix_lab.py**                                                                                  | End-to-end simulation of the Hendrix signal chain in Python; generates `.wav` stems and spectrograms. |
| **echo_ir.py**                                                                                                            | Simple delay/feedback impulse response plotter.                                                       |
| **plot_octavia_nuclear.py**, **plot_octavia_pretty.py**                                                                   | Idealized and SPICE-driven Octavia rectifier plots.                                                   |
| **requirements.txt**                                                                                                      | Python dependencies (create if not present).                                                          |
| **README.md**                                                                                                             | This file.                                                                                            |

---

## ▶️ Running the Build

To reproduce all ngspice analyses and plots:

```bash
make all
```

This will:

1. Run each `.cir` netlist through ngspice in batch mode,
2. Generate `.dat` WRDATA files in `out/data/`,
3. Invoke the Python utilities to collapse, merge, and plot,
4. Produce IEEE-sized SVGs in `out/figs/`.

For a clean rebuild:

```bash
make clean
```

### Generate audio demonstrations

```bash
python hendrix_lab.py
```

Exports `.wav` stems for each block in the signal chain (fuzz, Octavia, wah, Uni-Vibe, Leslie, amp) at 48 kHz / 24-bit.

### Individual figures

Examples:

```bash
python plot_spice.py --ieee --in out/data/fuzz_si_ac.dat
python merge_bode.py out/data/wah_*.dat --out out/figs/wah_overlay.svg
python plot_octavia_nuclear.py
python plot_octavia_pretty.py
```

---

## 🧩 Data Flow

```
.cir  →  ngspice WRDATA (.dat)
.dat  →  wr_collapse.py / bode_quotient.py
.csv  →  merge_bode.py / wah_q_table.py
.svg  →  figures in manuscript
```

---

## 📊 Figure Mapping

| Figure (ODT)        | Script(s)                                           | Source data                                     |
| ------------------- | --------------------------------------------------- | ----------------------------------------------- |
| Fig. 1–6 Fuzz Face  | `bode_quotient.py`, `plot_spice.py`                 | `fuzzface_si.cir`, `fuzzface_ge_pnp_posgnd.cir` |
| Fig. 7 Octavia      | `plot_octavia_nuclear.py`, `plot_octavia_pretty.py` | `octavia_transformer_rect.cir`                  |
| Fig. 8–9 Wah        | `merge_bode.py`, `wah_q_table.py`                   | `vox_wah_param.cir`                             |
| Fig. 10–11 Uni-Vibe | `merge_bode.py`                                     | `univibe_frozen_lfo*.cir`                       |
| Spectrograms        | `hendrix_lab.py`                                    | internal synthetic chain                        |

All plots were exported as SVG at IEEE column width (3.25 in).

---

## 🧠 Notes

* The Fuzz Face decks use corrected emitter connections (`Q1 C1 B1 E1 …`, etc.).
* Germanium vs. silicon variants differ only in transistor models and polarity.
* The `Makefile` sets ngspice options for reproducible WRDATA output:

  ```
  .options numdgt=15 reltol=1e-5 abstol=1e-9 vabstol=1e-6
  .control
  set wr_singlescale
  set wr_vecnames
  set wr_noindex
  .endc
  ```
* The `wah_q_table.py` utility scans Bode data to find –3 dB edges and computes
  Q-factors automatically.
* The `chain_hendrix.py` and `hendrix_lab.py` scripts normalize only once at the
  end of the chain for realistic gain staging.

---

## 🧾 License and Citation

All code and SPICE decks © 2025 [Rohan Puranik].
Released under the **MIT License** unless stated otherwise.

If you use this material in research or teaching, please cite:

> [Your Name], “Hendrix, Systems Engineer: Rebuilding a Guitar Hero’s Signal Chain with SPICE,” GitHub repository, 2025.
> DOI: *(Zenodo DOI if minted)*

---

## 🧩 Acknowledgments

Based on circuit analyses of the Fuzz Face, Octavia, Vox V847 Wah, and Uni-Vibe
effects described in the *Hendrix FactPack 2025* and accompanying article.
ngspice 42.1 and Python 3.11 were used for all analyses and figure generation.

```
