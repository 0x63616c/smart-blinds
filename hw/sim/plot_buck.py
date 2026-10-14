"""Plot ngspice output from buck_pd12v6mini.cir (wrdata columns: t,vout, t,iL, t,vsw, t,vbus, t,isrc)."""
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = pd.read_csv("buck_wave.txt", sep=r"\s+", header=None, usecols=[0, 1, 3, 5, 7], names=["t", "vout", "il", "vsw", "vbus"])
d["t"] *= 1e3                                            # ms
ink, accent, grid = "#1f2328", "#d1495b", "#e6e6e6"
fig, ax = plt.subplots(2, 2, figsize=(13, 7.5))
def style(a, title, ylabel):
    a.set_title(title, loc="left", fontsize=11, color=ink); a.set_ylabel(ylabel); a.grid(color=grid); a.spines[["top", "right"]].set_visible(False)
s = d[::200]
a = ax[0, 0]; a.plot(s.t, s.vout, color=ink, lw=1.2)
a.axvline(6, color=accent, ls="--", lw=1); a.text(6.1, 4, "load 1 A → 5 A", color=accent)
a.text(0.7, 13.3, "2 ms soft start", color="#555")
style(a, "Output voltage: start-up, then a load step", "V out (V)"); a.set_xlabel("time (ms)"); a.set_ylim(0, 14.5)
w = d[(d.t > 9.990) & (d.t < 10.0)]
a = ax[0, 1]; a.plot((w.t - 9.99) * 1e3, w.vout * 1e3 - 12600, color=ink, lw=1.2)
style(a, f"Output ripple at 5 A: {(w.vout.max()-w.vout.min())*1e3:.0f} mV peak-to-peak", "V out − 12.6 V (mV)"); a.set_xlabel("time (µs)")
a = ax[1, 0]; a.plot((w.t - 9.99) * 1e3, w.il, color=ink, lw=1.2)
a.axhline(8.6, color=accent, ls="--", lw=1); a.text(0.2, 8.0, "L1 saturates at 8.6 A", color=accent)
a.axhline(5, color="#888", ls=":", lw=1); a.text(0.2, 5.15, "5 A load", color="#666")
style(a, f"Inductor current at 5 A: {w.il.min():.1f} to {w.il.max():.1f} A", "I L1 (A)"); a.set_xlabel("time (µs)"); a.set_ylim(0, 9.5)
a = ax[1, 1]; a.plot((w.t - 9.99) * 1e3, w.vsw, color=ink, lw=1.2)
style(a, "Switching node: U1 flips L1 between 20 V and 0 V", "V switch node (V)"); a.set_xlabel("time (µs)")
fig.suptitle("pd12v6mini buck, ngspice: 20 V in, 12.6 V out (U1 stood in by ideal switches + current-mode loop)", fontsize=12, color=ink, x=0.01, ha="left")
fig.tight_layout(); fig.savefig("buck_pd12v6mini.png", dpi=130)
