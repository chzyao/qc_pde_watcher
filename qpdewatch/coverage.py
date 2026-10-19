"""Coverage matrix and the two gap-map figures.

Requires matplotlib; everything else in the pipeline is stdlib-only, so this
module is imported lazily by the CLI and can be skipped in CI.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .config import DATA_DIR, DOCS_DIR, Vocabularies

MIN_FAMILY_SIZE = 5  # families below this are too small to read as a row


def _split(cell: str) -> list[str]:
    return [p for p in (x.strip() for x in cell.split(";")) if p]


def statistical_rows(rows: list[dict]) -> list[dict]:
    """The subset every coverage number is computed over.

    Adjacent-tier papers are not about PDEs, and abstract-less records can only
    be tagged from a title — counting either as "a paper that does not address
    axis X" would depress every percentage for a bibliographic reason rather
    than a scientific one.
    """
    return [r for r in rows if r.get("tier", "core") == "core" and r.get("has_abstract", True)]


def coverage_matrix(rows: list[dict], vocab: Vocabularies, cfd_only: bool = True):
    """Return (families, axes, counts, fractions, family_sizes)."""
    rows = statistical_rows(rows)
    subset = [r for r in rows if r["cfd_facing"]] if cfd_only else rows
    axes = list(vocab.capability_axes)
    sizes = {f: sum(1 for r in subset if f in _split(r["algorithm_families"]))
             for f in vocab.algorithm_families}
    families = sorted([f for f, n in sizes.items() if n >= MIN_FAMILY_SIZE],
                      key=lambda f: -sizes[f])
    counts = [[sum(1 for r in subset
                   if f in _split(r["algorithm_families"]) and c in _split(r["capability_axes"]))
               for c in axes] for f in families]
    fractions = [[counts[i][j] / sizes[f] for j in range(len(axes))]
                 for i, f in enumerate(families)]
    # Order columns by overall coverage so the gap frontier is on the right.
    order = sorted(range(len(axes)),
                   key=lambda j: -sum(counts[i][j] for i in range(len(families))))
    axes = [axes[j] for j in order]
    counts = [[row[j] for j in order] for row in counts]
    fractions = [[row[j] for j in order] for row in fractions]
    return families, axes, counts, fractions, sizes


def scorecard(rows: list[dict], vocab: Vocabularies, split_year: int = 2024) -> list[dict]:
    """Per-axis coverage before and from `split_year`, over CFD-facing papers."""
    cfd = [r for r in statistical_rows(rows) if r["cfd_facing"] and r["year"]]
    early = [r for r in cfd if r["year"] < split_year]
    recent = [r for r in cfd if r["year"] >= split_year]
    out = []
    for axis in vocab.capability_axes:
        n_e = sum(1 for r in early if axis in _split(r["capability_axes"]))
        n_r = sum(1 for r in recent if axis in _split(r["capability_axes"]))
        out.append({
            "capability_axis": axis,
            f"n_pre_{split_year}": n_e, f"n_from_{split_year}": n_r,
            f"pct_pre_{split_year}": round(100 * n_e / len(early), 1) if early else 0.0,
            f"pct_from_{split_year}": round(100 * n_r / len(recent), 1) if recent else 0.0,
        })
    out.sort(key=lambda d: d[f"pct_from_{split_year}"])
    return out


def write_tables(rows: list[dict], vocab: Vocabularies, outdir: Path | None = None) -> list[Path]:
    outdir = outdir or DATA_DIR
    families, axes, counts, fractions, sizes = coverage_matrix(rows, vocab)
    written = []
    for name, grid in (("coverage_matrix_counts.csv", counts),
                       ("coverage_matrix_fraction.csv", fractions)):
        path = outdir / name
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["algorithm_family", "n_papers"] + axes)
            for f, grid_row in zip(families, grid):
                w.writerow([f, sizes[f]] + [round(v, 3) if isinstance(v, float) else v
                                            for v in grid_row])
        written.append(path)
    card = scorecard(rows, vocab)
    path = outdir / "gap_scorecard.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(card[0]))
        w.writeheader()
        w.writerows(card)
    written.append(path)
    return written


def write_figures(rows: list[dict], vocab: Vocabularies, outdir: Path | None = None) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    outdir = outdir or DOCS_DIR
    outdir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "figure.dpi": 110,
                         "savefig.bbox": "tight"})
    written = []

    families, axes, counts, fractions, sizes = coverage_matrix(rows, vocab)
    short = lambda s: s.split(" (")[0].replace(" / ", " /\n")
    frac = np.array(fractions)
    fig, ax = plt.subplots(figsize=(11.6, 0.45 * len(families) + 2.6))
    im = ax.imshow(frac, cmap="magma_r", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(axes)), [short(a) for a in axes], rotation=38, ha="right")
    ax.set_yticks(range(len(families)),
                  [f"{f.split(' (')[0].split(' / ')[0]}  (n={sizes[f]})" for f in families])
    for i in range(len(families)):
        for j in range(len(axes)):
            ax.text(j, i, counts[i][j], ha="center", va="center", fontsize=6,
                    color="white" if frac[i, j] > 0.55 else "0.25")
    ax.set_xticks(np.arange(-0.5, len(axes), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(families), 1), minor=True)
    ax.grid(which="minor", color="white", lw=0.8)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, pad=0.012, fraction=0.028)
    cbar.set_label("Fraction of the family's papers that foreground the axis", fontsize=7)
    ax.set_title("Capability coverage by algorithm family, CFD-facing papers\n"
                 "Cell numbers are paper counts; columns ordered by overall coverage",
                 loc="left")
    path = outdir / "coverage_matrix.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    written.append(path)

    card = scorecard(rows, vocab)
    labels = [d["capability_axis"].split(" (")[0] for d in card]
    early = [d["pct_pre_2024"] for d in card]
    recent = [d["pct_from_2024"] for d in card]
    y = np.arange(len(card))
    fig2, ax2 = plt.subplots(figsize=(7.6, 0.33 * len(card) + 1.8))
    for i in y:
        ax2.plot([early[i], recent[i]], [i, i], color="0.78", lw=1.6,
                 zorder=1, solid_capstyle="round")
    ax2.scatter(early, y, s=26, color="0.55", zorder=3, label="before 2024")
    ax2.scatter(recent, y, s=34, color="#B5179E", zorder=3, label="2024 onward")
    ax2.set_yticks(y, labels)
    ax2.set_xlabel("% of CFD-facing papers in the window that foreground the axis"
                   "   (right = better covered)")
    ax2.margins(0.06)
    ax2.grid(axis="x", color="0.92", lw=0.7)
    ax2.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax2.spines[side].set_visible(False)
    ax2.legend(frameon=False, fontsize=7, loc="lower right")
    ax2.set_title("Which capability gaps are closing", loc="left")
    path2 = outdir / "gap_trajectory.png"
    fig2.savefig(path2, dpi=300)
    plt.close(fig2)
    written.append(path2)
    return written
