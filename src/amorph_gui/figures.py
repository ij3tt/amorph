"""
The previews of the figures of amorph_tex on «Сравнение», drawn with
matplotlib from the pooled runs (amorph_seeds.pool) on a Figure: the same
curves as the .tex files draw, so that what LaTeX makes can be seen
without LaTeX, and saved as PNG. Nothing here needs Qt.
"""

import numpy as np

from amorph_gui import theme

# The colours of doc/figures/xrd_fit_body.tex
FIT_GREEN = (0.0, 0.62, 0.0)
FIT_GOLD = (0.75, 0.58, 0.12)

# One colour per seed, as in doc/figures/xrd_seeds_body.tex
SEED_COLORS = ["#0F766E", "#B45309", "#6D28D9", "#BE185D", "#15803D",
               "#0369A1"]


def _seed_label(seed, i):
    return "seed {0}".format(seed) if seed is not None \
        else "run {0}".format(i + 1)


def draw_fit(fig, pooled, title):
    """
    The figure of doc/figures/xrd_fit.tex: the data, the posterior means of
    the model, the amorphous part, the crystalline peaks and the
    background, and faint posterior samples.
    """
    x, y, c = pooled["x"], pooled["y"], pooled["curves"]
    ex = pooled["examples"]
    ax = fig.add_subplot(1, 1, 1)
    for i in range(len(ex["model_curve"])):
        ax.plot(x, ex["model_curve"][i], color=FIT_GREEN, alpha=0.28,
                lw=0.35)
        ax.plot(x, ex["wide"][i], color="blue", alpha=0.28, lw=0.35)
        ax.plot(x, ex["narrow"][i], color="red", alpha=0.28, lw=0.35)
    ax.plot(x, c["model_curve"], color=FIT_GREEN, lw=2.0,
            label="Model (mean)")
    ax.plot(x, c["wide"], "--", color="blue", lw=1.6,
            label="Amorphous (mean)")
    ax.plot(x, c["narrow"], "--", color="red", lw=1.6,
            label="Crystalline peaks (mean)")
    ax.plot(x, c["bg"], "--", color=FIT_GOLD, lw=1.6,
            label="Background (mean)")
    ax.plot(x, y, "o", mfc="none", mec="black", ms=3.0, mew=0.5, alpha=0.75,
            label="Experimental")
    ymax = 50.0 * np.ceil(1.2 * max(y.max(), np.max(c["model_curve"]))
                          / 50.0)
    ax.set_xlim(np.floor(x.min()), np.ceil(x.max()))
    ax.set_ylim(0, ymax)
    ax.set_xlabel("$2\\theta$, °")
    ax.set_ylabel("Intensity, arb. un.")
    ax.set_title(title, fontweight="bold")
    ax.text(0.025, 0.96, "Amorphous = {0:.1f}%".format(100.0 * pooled["mean"]),
            transform=ax.transAxes, va="top")
    handles, labels = ax.get_legend_handles_labels()
    order = [4, 0, 1, 2, 3]
    ax.legend([handles[i] for i in order], [labels[i] for i in order],
              loc="upper right", frameon=False)


def draw_seeds(fig, pooled, title):
    """
    The figure of doc/figures/xrd_seeds.tex: (a) the data with the
    background, the amorphous halo, the crystalline peaks, the model and
    its 90% band, and the halo of each seed; (b) the distribution of the
    fraction of each seed and pooled.
    """
    x, y, c = pooled["x"], pooled["y"], pooled["curves"]
    seeds = pooled["seeds"]
    grid = fig.add_gridspec(1, 2, width_ratios=[2.0, 1.0])
    ax = fig.add_subplot(grid[0])
    lo, hi = pooled["band"]
    halo = c["bg"] + c["wide"]
    ax.fill_between(x, lo, hi, color=theme.BAND, lw=0, label="model, 90%")
    ax.fill_between(x, c["bg"], halo, color=theme.WIDE_FILL, alpha=0.75,
                    lw=0)
    ax.fill_between(x, halo, np.maximum(c["model_curve"], halo),
                    color=theme.NARROW_FILL, alpha=0.6, lw=0,
                    label="crystalline peaks")
    ax.plot(x, c["bg"], "--", color=theme.BACKGROUND, lw=1.0,
            label="background")
    ax.plot(x, halo, color=theme.WIDE, lw=1.4, label="amorphous halo")
    if len(seeds) > 1:
        for i, h in enumerate(pooled["halos"]):
            ax.plot(x, h, ":", color=SEED_COLORS[i % len(SEED_COLORS)],
                    lw=1.0)
    ax.plot(x, y, "o", color=theme.DATA_LIGHT, ms=1.6, mew=0)
    ax.plot(x, c["model_curve"], color=theme.INK, lw=1.1,
            label="model (mean)")
    q = pooled["quantiles"]
    spread = "one run" if pooled["spread"] is None else \
        "spread of the medians of the seeds {0:.3f}".format(pooled["spread"])
    ax.text(0.02, 0.97, "amorphous fraction {0:.3f}\n50%: [{1:.3f}, {2:.3f}]"
            "\n90%: [{3:.3f}, {4:.3f}]\n{5}".format(q[2], q[1], q[3], q[0],
                                                     q[4], spread),
            transform=ax.transAxes, va="top", fontsize=8)
    ax.set_xlim(np.floor(x.min()), np.ceil(x.max()))
    ax.set_ylim(0, 50.0 * np.ceil(1.2 * max(y.max(), np.max(hi)) / 50.0))
    ax.set_xlabel("$2\\theta$, °")
    ax.set_ylabel("Intensity, counts")
    known = [str(s) for s in seeds if s is not None]
    ax.set_title("(a) " + title + (", seeds " + ", ".join(known)
                                   if len(known) > 1 else ""), fontsize=9)
    ax.legend(loc="upper right", fontsize=7)

    ax = fig.add_subplot(grid[1])
    h = pooled["histogram"]
    edges = h["edges"]
    centres = 0.5 * (edges[1:] + edges[:-1])
    ax.fill_between(centres, h["pooled"], step="mid", color=theme.WIDE_FILL,
                    label="pooled")
    ax.step(centres, h["pooled"], where="mid", color=theme.WIDE, lw=0.8)
    for i, density in enumerate(h["densities"]):
        ax.step(centres, density, where="mid",
                color=SEED_COLORS[i % len(SEED_COLORS)], lw=1.0,
                label=_seed_label(seeds[i], i))
    ax.set_xlim(edges[0], edges[-1])
    ax.set_ylim(0)
    ax.set_xlabel("amorphous fraction")
    ax.set_ylabel("posterior density")
    ax.set_title("(b) {0}".format("{0} seeds and pooled".format(len(seeds))
                                  if len(seeds) > 1 else "the fraction"),
                 fontsize=9)
    ax.legend(loc="upper left", fontsize=7)


# The figures by style, as amorph_tex.FIGURES names them
DRAW = {"fit": draw_fit, "seeds": draw_seeds}
