"""Draw the archived Budapest LiDAR scan used for the same-input steering test."""
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "results" / "article"
data = json.loads((OUT / "repair-data.json").read_text())
steps = [step for step, _ in data["models"]["original"]["same_input_step_steering"]]
with gzip.open(OUT / data["scan_archive"], "rb") as archive:
    scan = np.load(archive)[steps.index(data["focus_step"])]
meters = 15 * (scan.astype(float) + 1)
selected = np.arange(880, 920)
mean_cm = 100 * meters[selected].mean()
for lang in ("it", "en"):
    it = lang == "it"
    title = "I 40 raggi che leggono il muro" if it else "The 40 beams that see the wall"
    with plt.rc_context({"svg.fonttype": "none", "svg.hashsalt": "budapest-lidar"}):
        fig, axes = plt.subplots(2, figsize=(7, 4.7), layout="constrained")
        fig.patch.set_facecolor("#fcfbf7")
        fig.suptitle(title, fontsize=21, fontfamily="serif")
        ax, zoom = axes
        ax.plot(meters, color="#465650", linewidth=1)
        ax.axvspan(880, 919, color="#c44e23", alpha=.45)
        ax.set(xlim=(0, 1079), ylabel="m", title="Budapest  ·  6,10 s  ·  LiDAR" if it else "Budapest  ·  6.10 s  ·  LiDAR")
        zoom.plot(selected, meters[selected] * 100, color="#ac421c", marker=".", linewidth=1)
        zoom.axhline(mean_cm, color="#334d43", ls="--", label=("media" if it else "mean") + f"  {mean_cm:.1f} cm".replace(".", "," if it else "."))
        zoom.set(xlim=(880, 919), ylabel="cm", xlabel="Indice del raggio" if it else "Beam index")
        zoom.legend(loc="best", frameon=False)
        for panel in axes:
            panel.set_facecolor("#fcfbf7")
            panel.spines[["top", "right"]].set_visible(False)
        path = OUT / f"lidar-{lang}.svg"
        fig.savefig(path, metadata={"Date": None, "Title": title})
        description = "Budapest 1101 · LiDAR 0–1079 · zoom 880–919"
        path.write_text(path.read_text().replace("</title>", f"</title><desc>{description}</desc>", 1))
        plt.close(fig)
