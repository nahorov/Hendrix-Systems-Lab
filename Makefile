# =========================
# Hendrix Lab — Makefile (clean)
# =========================

SHELL          := /bin/bash
.ONESHELL:
.SHELLFLAGS    := -eu -o pipefail -c

PY             ?= python3
NGSPICE        ?= ngspice

OUT            := out
DATA           := $(OUT)/data
FIGS           := $(OUT)/figs
LOGS           := $(OUT)/logs

# ---------- Netlists ----------
WAH_NET        := vox_wah_param.cir
VIBE_NET       := univibe_frozen_lfo.cir
VIBE_SWEEP     := univibe_frozen_lfo_sweep.cir
OCT_NET        := octavia_behavioral.cir
FF_SI_NET      := fuzzface_si.cir
FF_GE_NET      := fuzzface_ge_pnp_posgnd.cir

# ---------- Python tools ----------
PLOT           := plot_spice.py
MERGE          := merge_bode.py
QTABLE         := wah_q_table.py
BQ             := bode_quotient.py
WC			   := wr_collapse.py

# ---------- Global knobs ----------
# AC sweep (change here if you want different resolution / span)
AC_MODE        ?= dec
AC_NPTS        ?= 200
AC_FSTART      ?= 20
AC_FSTOP       ?= 20k
AC_ARGS        := $(AC_MODE) $(AC_NPTS) $(AC_FSTART) $(AC_FSTOP)

# Transient defaults (440 Hz tone -> 50 ms ≈ 22 cycles)
TRAN_TSTEP     ?= 0.1ms
TRAN_TSTOP     ?= 50ms
TRAN_TSTART    ?= 0
TRAN_TMAX      ?= 1us
TRAN_ARGS      := $(TRAN_TSTEP) $(TRAN_TSTOP) $(TRAN_TSTART) $(TRAN_TMAX)

# Output node aliases (override if your decks use different names)
WAH_OUT_NODE   ?= v(out)
VIBE_OUT_NODE  ?= v(out)
OCT_OUT_NODE   ?= v(out)
FF_OUT_NODE    ?= v(out)   # for time-domain plots

# ---------- Outputs ----------
WAH_AC_RAW       := $(DATA)/wah_ac.dat
WAH_MAG_SVG      := $(FIGS)/wah_mag.svg
WAH_PHASE_SVG    := $(FIGS)/wah_phase.svg

VIBE_AC_RAW      := $(DATA)/vibe_ac.dat
VIBE_MAG_SVG     := $(FIGS)/vibe_mag.svg
VIBE_PHASE_SVG   := $(FIGS)/vibe_phase.svg

# Optional sweep overlays
VIBE_SWEEP_LIST  := $(DATA)/vibe_R6k.dat $(DATA)/vibe_R12k.dat $(DATA)/vibe_R22k.dat \
                    $(DATA)/vibe_R33k.dat $(DATA)/vibe_R47k.dat $(DATA)/vibe_R68k.dat
VIBE_SWEEP_MAG   := $(FIGS)/vibe_positions_mag.svg
VIBE_SWEEP_PHASE := $(FIGS)/vibe_positions_phase.svg

OCT_TRAN_RAW     := $(DATA)/oct_tran.dat
OCT_TIME_SVG     := $(FIGS)/oct_time.svg

FF_SI_AC_RAW     := $(DATA)/ff_ac.dat
FF_SI_TRAN_RAW   := $(DATA)/ff_tran.dat
FF_SI_ZIN_MAG    := $(FIGS)/ff_si_zin_mag.svg
FF_SI_ZIN_PHASE  := $(FIGS)/ff_si_zin_phase.svg
FF_SI_TIME_SVG   := $(FIGS)/ff_si_time.svg

FF_GE_AC_RAW     := $(DATA)/ff_ge_ac.dat
FF_GE_TRAN_RAW   := $(DATA)/ff_ge_tran.dat
FF_GE_ZIN_MAG    := $(FIGS)/ff_ge_zin_mag.svg
FF_GE_ZIN_PHASE  := $(FIGS)/ff_ge_zin_phase.svg
FF_GE_TIME_SVG   := $(FIGS)/ff_ge_time.svg

# ---------- Phony ----------
.PHONY: all clean verify wah vibe vibe-sweep octavia fuzz-si fuzz-ge figs dirs

# Default: build everything we showcase
all: dirs wah vibe octavia fuzz-si fuzz-ge verify
	@echo "All done ✅  See SVGs under $(FIGS)/"

# Dirs
dirs: $(OUT) $(DATA) $(FIGS) $(LOGS)
$(OUT) $(DATA) $(FIGS) $(LOGS):
	mkdir -p $@

# =========================
# WAH (AC magnitude + phase)
# =========================

WAH_AC_RAW   := $(DATA)/wah_ac.dat
WAH_AC_CLEAN := $(DATA)/wah_ac_clean.dat
WAH_MAG_SVG  := $(FIGS)/wah_mag.svg
WAH_PHASE_SVG:= $(FIGS)/wah_phase.svg

$(WAH_AC_RAW): $(WAH_NET) | dirs
	printf "%s\n" \
	  "wah_driver" \
	  ".control" \
	  "set noaskquit" \
	  "source $(WAH_NET)" \
	  "reset" \
	  "ac $(AC_ARGS)" \
	  "set wr_singlescale" \
	  "set wr_vecnames" \
	  "set wr_noindex" \
	  "set filetype=ascii" \
	  "wrdata $(WAH_AC_RAW) frequency real($(WAH_OUT_NODE)) imag($(WAH_OUT_NODE))" \
	  "quit" \
	  ".endc" \
	  ".end" > $(LOGS)/wah_cmd.cir
	$(NGSPICE) -b -o $(LOGS)/wah.log $(LOGS)/wah_cmd.cir
	@test -s $(WAH_AC_RAW) || { echo "WRDATA missing: $(WAH_AC_RAW)"; sed -n '1,200p' $(LOGS)/wah.log; exit 1; }

$(WAH_AC_CLEAN): $(WAH_AC_RAW) $(WC) | dirs
	$(PY) $(WC) $(WAH_AC_RAW) $(WAH_AC_CLEAN)

$(WAH_MAG_SVG) $(WAH_PHASE_SVG): $(WAH_AC_CLEAN) $(PLOT) | dirs
	$(PY) $(PLOT) bode-svg $(WAH_AC_CLEAN) \
	  --fcol frequency \
	  --yr re --yi im \
	  --title "Wah – Magnitude" \
	  --out $(WAH_MAG_SVG) --phase-out $(WAH_PHASE_SVG)

wah: $(WAH_MAG_SVG) $(WAH_PHASE_SVG)


# =========================
# VIBE (AC magnitude + phase)
# =========================

VIBE_AC_RAW    := $(DATA)/vibe_ac.dat
VIBE_AC_CLEAN  := $(DATA)/vibe_ac_clean.dat
VIBE_MAG_SVG   := $(FIGS)/vibe_mag.svg
VIBE_PHASE_SVG := $(FIGS)/vibe_phase.svg

$(VIBE_AC_RAW): $(VIBE_NET) | dirs
	printf "%s\n" \
	  "vibe_driver" \
	  ".control" \
	  "set noaskquit" \
	  "source $(VIBE_NET)" \
	  "reset" \
	  "ac $(AC_ARGS)" \
	  "set wr_singlescale" \
	  "set wr_vecnames" \
	  "set wr_noindex" \
	  "set filetype=ascii" \
	  "wrdata $(VIBE_AC_RAW) frequency real($(VIBE_OUT_NODE)) imag($(VIBE_OUT_NODE))" \
	  "quit" \
	  ".endc" \
	  ".end" > $(LOGS)/vibe_cmd.cir
	$(NGSPICE) -b -o $(LOGS)/vibe.log $(LOGS)/vibe_cmd.cir
	@test -s $(VIBE_AC_RAW) || { echo "WRDATA missing: $(VIBE_AC_RAW)"; sed -n '1,200p' $(LOGS)/vibe.log; exit 1; }

$(VIBE_AC_CLEAN): $(VIBE_AC_RAW) $(WC) | dirs
	$(PY) $(WC) $(VIBE_AC_RAW) $(VIBE_AC_CLEAN)

$(VIBE_MAG_SVG) $(VIBE_PHASE_SVG): $(VIBE_AC_CLEAN) $(PLOT) | dirs
	$(PY) $(PLOT) bode-svg $(VIBE_AC_CLEAN) \
	  --fcol frequency \
	  --yr re --yi im \
	  --title "Uni-Vibe (Frozen LFO) – Magnitude" \
	  --out $(VIBE_MAG_SVG) --phase-out $(VIBE_PHASE_SVG)

vibe: $(VIBE_MAG_SVG) $(VIBE_PHASE_SVG)


# -------------------------
# VIBE sweep overlay (opt.)
# -------------------------
$(VIBE_SWEEP_LIST): $(VIBE_SWEEP) $(VIBE_NET) | dirs
	$(NGSPICE) -b -o $(LOGS)/vibe_sweep.log $(VIBE_SWEEP)
	@for f in $(VIBE_SWEEP_LIST); do \
	  test -s $$f || { echo "Missing $$f (see $(LOGS)/vibe_sweep.log)"; exit 1; }; \
	done

$(VIBE_SWEEP_MAG) $(VIBE_SWEEP_PHASE): $(MERGE) $(VIBE_SWEEP_LIST) | dirs
	$(PY) $(MERGE) \
	  --out-mag $(VIBE_SWEEP_MAG) \
	  --out-phase $(VIBE_SWEEP_PHASE) \
	  --title "Uni-Vibe — Magnitude" \
	  --fcol frequency --recol "real($(VIBE_OUT_NODE))" --imcol "imag($(VIBE_OUT_NODE))" \
	  $(DATA)/vibe_R6k.dat:"6k"   \
	  $(DATA)/vibe_R12k.dat:"12k" \
	  $(DATA)/vibe_R22k.dat:"22k" \
	  $(DATA)/vibe_R33k.dat:"33k" \
	  $(DATA)/vibe_R47k.dat:"47k" \
	  $(DATA)/vibe_R68k.dat:"68k"

vibe-sweep: $(VIBE_SWEEP_MAG) $(VIBE_SWEEP_PHASE)


# =========================
# OCTAVIA (Python-only, ideal)
# =========================

OCT_TIME_SVG := $(FIGS)/octavia_time.svg

$(OCT_TIME_SVG): plot_octavia_nuclear.py | dirs
	$(PY) plot_octavia_nuclear.py

octavia: $(OCT_TIME_SVG)



# =========================
# Fuzz Face — Silicon (NPN)
# =========================

$(FF_SI_AC_RAW): $(FF_SI_NET) | dirs
	printf "%s\n" \
	  "ff_si_ac_driver" \
	  ".control" \
	  "set noaskquit" \
	  "source $(FF_SI_NET)" \
	  "reset" \
	  "alter @Vsig[acmag]=1" \
	  "ac $(AC_ARGS)" \
	  "set wr_singlescale" \
	  "set wr_vecnames" \
	  "set wr_noindex" \
	  "set filetype=ascii" \
	  "wrdata $(FF_SI_AC_RAW) frequency real(v(in)) imag(v(in)) real(i(vsig)) imag(i(vsig))" \
	  "quit" \
	  ".endc" \
	  ".end" > $(LOGS)/ff_ac_cmd.cir
	$(NGSPICE) -b -o $(LOGS)/ff_ac.log $(LOGS)/ff_ac_cmd.cir
	@test -s $(FF_SI_AC_RAW) || { echo "WRDATA missing: $(FF_SI_AC_RAW)"; sed -n '1,200p' $(LOGS)/ff_ac.log; exit 1; }

$(FF_SI_TRAN_RAW): $(FF_SI_NET) | dirs
	printf "%s\n" \
	  "ff_si_tran_driver" \
	  ".control" \
	  "set noaskquit" \
	  "source $(FF_SI_NET)" \
	  "reset" \
	  "tran $(TRAN_ARGS)" \
	  "set wr_singlescale" \
	  "set wr_vecnames" \
	  "set filetype=ascii" \
	  "wrdata $(FF_SI_TRAN_RAW) time $(FF_OUT_NODE) v(b1) v(c2)" \
	  "quit" \
	  ".endc" \
	  ".end" > $(LOGS)/ff_tran_cmd.cir
	$(NGSPICE) -b -o $(LOGS)/ff_tran.log $(LOGS)/ff_tran_cmd.cir
	@test -s $(FF_SI_TRAN_RAW) || { echo "WRDATA missing: $(FF_SI_TRAN_RAW)"; sed -n '1,200p' $(LOGS)/ff_tran.log; exit 1; }

$(FF_SI_ZIN_MAG) $(FF_SI_ZIN_PHASE): $(FF_SI_AC_RAW) $(BQ) | dirs
	$(PY) $(BQ) $(FF_SI_AC_RAW) \
	  --fcol frequency \
	  --an "real(v(in))"  --ai "imag(v(in))" \
	  --bn "real(i(vsig))" --bi "imag(i(vsig))" \
	  --title "Fuzz Face (Si) — Input Impedance Magnitude" \
	  --out-mag $(FF_SI_ZIN_MAG) --out-phase $(FF_SI_ZIN_PHASE)

$(FF_SI_TIME_SVG): $(FF_SI_TRAN_RAW) $(PLOT) | dirs
	$(PY) $(PLOT) time-svg $(FF_SI_TRAN_RAW) \
	  --xcol time --ycols '$(FF_OUT_NODE)' 'v(b1)' 'v(c2)' \
	  --title "Fuzz Face (Si) — Time Domain" \
	  --out $(FF_SI_TIME_SVG)

fuzz-si: $(FF_SI_ZIN_MAG) $(FF_SI_ZIN_PHASE) $(FF_SI_TIME_SVG)


# =========================
# Fuzz Face — Germanium (PNP, pos. ground)
# =========================

$(FF_GE_AC_RAW): $(FF_GE_NET) | dirs
	printf "%s\n" \
	  "ff_ge_ac_driver" \
	  ".control" \
	  "set noaskquit" \
	  "source $(FF_GE_NET)" \
	  "reset" \
	  "alter @Vsig[acmag]=1" \
	  "ac $(AC_ARGS)" \
	  "set wr_singlescale" \
	  "set wr_vecnames" \
	  "set wr_noindex" \
	  "set filetype=ascii" \
	  "wrdata $(FF_GE_AC_RAW) frequency real(v(in)) imag(v(in)) real(i(vsig)) imag(i(vsig))" \
	  "quit" \
	  ".endc" \
	  ".end" > $(LOGS)/ff_ge_ac_cmd.cir
	$(NGSPICE) -b -o $(LOGS)/ff_ge_ac.log $(LOGS)/ff_ge_ac_cmd.cir
	@test -s $(FF_GE_AC_RAW) || { echo "WRDATA missing: $(FF_GE_AC_RAW)"; sed -n '1,200p' $(LOGS)/ff_ge_ac.log; exit 1; }

$(FF_GE_TRAN_RAW): $(FF_GE_NET) | dirs
	printf "%s\n" \
	  "ff_ge_tran_driver" \
	  ".control" \
	  "set noaskquit" \
	  "source $(FF_GE_NET)" \
	  "reset" \
	  "tran $(TRAN_ARGS)" \
	  "set wr_singlescale" \
	  "set wr_vecnames" \
	  "set filetype=ascii" \
	  "wrdata $(FF_GE_TRAN_RAW) time $(FF_OUT_NODE) v(b1) v(c2)" \
	  "quit" \
	  ".endc" \
	  ".end" > $(LOGS)/ff_ge_tran_cmd.cir
	$(NGSPICE) -b -o $(LOGS)/ff_ge_tran.log $(LOGS)/ff_ge_tran_cmd.cir
	@test -s $(FF_GE_TRAN_RAW) || { echo "WRDATA missing: $(FF_GE_TRAN_RAW)"; sed -n '1,200p' $(LOGS)/ff_ge_tran.log; exit 1; }

$(FF_GE_ZIN_MAG) $(FF_GE_ZIN_PHASE): $(FF_GE_AC_RAW) $(BQ) | dirs
	$(PY) $(BQ) $(FF_GE_AC_RAW) \
	  --fcol frequency \
	  --an "real(v(in))"  --ai "imag(v(in))" \
	  --bn "real(i(vsig))" --bi "imag(i(vsig))" \
	  --title "Fuzz Face (Ge/PNP) — Input Impedance Magnitude" \
	  --out-mag $(FF_GE_ZIN_MAG) --out-phase $(FF_GE_ZIN_PHASE)

$(FF_GE_TIME_SVG): $(FF_GE_TRAN_RAW) $(PLOT) | dirs
	$(PY) $(PLOT) time-svg $(FF_GE_TRAN_RAW) \
	  --xcol time --ycols '$(FF_OUT_NODE)' 'v(b1)' 'v(c2)' \
	  --title "Fuzz Face (Ge/PNP) — Time Domain" \
	  --out $(FF_GE_TIME_SVG)

fuzz-ge: $(FF_GE_ZIN_MAG) $(FF_GE_ZIN_PHASE) $(FF_GE_TIME_SVG)

# =========================
# Meta targets
# =========================

figs: $(WAH_MAG_SVG) $(WAH_PHASE_SVG) \
      $(VIBE_MAG_SVG) $(VIBE_PHASE_SVG) \
      $(OCT_TIME_SVG) \
      $(FF_SI_ZIN_MAG) $(FF_SI_ZIN_PHASE) $(FF_SI_TIME_SVG) \
      $(FF_GE_ZIN_MAG) $(FF_GE_ZIN_PHASE) $(FF_GE_TIME_SVG)

verify:
	@test -s $(WAH_MAG_SVG)   || { echo "Missing $(WAH_MAG_SVG)"; exit 1; }
	@test -s $(VIBE_MAG_SVG)  || { echo "Missing $(VIBE_MAG_SVG)"; exit 1; }
	@test -s $(OCT_TIME_SVG)  || { echo "Missing $(OCT_TIME_SVG)"; exit 1; }
	@test -s $(FF_SI_ZIN_MAG) || { echo "Missing $(FF_SI_ZIN_MAG)"; exit 1; }
	@test -s $(FF_GE_ZIN_MAG) || { echo "Missing $(FF_GE_ZIN_MAG)"; exit 1; }
	@echo "verify: looks good ✅"

clean:
	rm -rf $(OUT)

