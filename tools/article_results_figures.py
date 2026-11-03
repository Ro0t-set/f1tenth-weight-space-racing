"""Rebuild article figures from the archived paired evaluations and weight manifests."""
from collections import Counter
import json
from io import StringIO
from pathlib import Path
from statistics import mean, median
from xml.sax.saxutils import escape

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
LOCKED = ROOT / "results/arc_recovery/locked"
OUT = ROOT / "results/article"
MODELS = ("ppo", "previous", "speed", "candidate")
INK, MUTED, PAPER, LINE = "#24251f", "#514f46", "#fcfbf7", "#d9d6cc"
COLORS = ("#186359", "#945b0c", "#a03823", "#656975")

LABELS = {
    "en": {
        "outcomes": "How the 105 starts ended",
        "out_sub": "21 circuits × 5 starts per controller",
        "groups": ("Finished", "Unfinished"),
        "categories": ("Clean", "Contact", "Collision", "Timeout"),
        "models": ("Edited PPO", "Previous arc", "Speed only", "Nose guard"),
        "out_note": "Contact = body touched or overlapped a wall in a saved pose.",
        "pace": "Lap time on matched starts",
        "pace_sub": "Nose guard against two references · 86 starts",
        "versus": ("Against previous arc", "Against edited PPO"),
        "mean": "Mean", "median": "median", "faster": "faster",
        "order": "Start number, ordered by circuit and seed",
        "zero": "0% = equal time. Negative values favour nose guard.",
        "outlier": "Oschersleben · seed 73404",
        "description": "Percentage change in lap time on starts finished by all three controllers.",
    },
    "it": {
        "outcomes": "Esito delle 105 partenze",
        "out_sub": "21 circuiti × 5 partenze per controllore",
        "groups": ("Giro completato", "Giro interrotto"),
        "categories": ("Pulito", "Contatto", "Collisione", "Timeout"),
        "models": ("PPO modificata", "Arco precedente", "Solo passo", "Nose guard"),
        "out_note": "Contatto = carrozzeria a contatto col muro in una posa salvata.",
        "pace": "Tempo sul giro a parità di partenza",
        "pace_sub": "Nose guard rispetto ai due riferimenti · 86 partenze",
        "versus": ("Rispetto all’arco precedente", "Rispetto alla PPO modificata"),
        "mean": "Media", "median": "mediana", "faster": "più rapidi",
        "order": "Partenze in ordine di circuito e seed",
        "zero": "0% = stesso tempo. I valori negativi favoriscono nose guard.",
        "outlier": "Oschersleben · seed 73404",
        "description": "Variazione percentuale del tempo sui giri completati da tutti e tre i controllori.",
    },
}



def read_pretrained():
    folder = ROOT / "results/ultra"
    comparison = json.loads((folder / "comparison_fast.json").read_text())
    manifest = json.loads((ROOT / "artifacts/ultra/wall_panic_fast.json").read_text())
    source = json.loads((ROOT / "artifacts/clearance_cautious.json").read_text())
    base, edit = (json.loads((folder / f"final_{k}.json").read_text()) for k in ("original", "fast"))
    assert base["sha256"] == manifest["source_sha256"] == source["source_sha256"]
    assert edit["sha256"] == manifest["sha256"]
    rows = [{(r["map"], r["seed"]): r for r in d["rows"]} for d in (base, edit)]
    base_rows, edit_rows = rows
    assert base_rows.keys() == edit_rows.keys()
    states, times = {}, []
    for key, a in base_rows.items():
        b = edit_rows[key]
        assert a["start"] == b["start"]
        assert all(not r["timeout"] and r["success"] != r["collision"] for r in (a, b))
        states[key] = (a["success"], b["success"])
        if all(states[key]):
            times.append(100 * (b["seconds"] / a["seconds"] - 1))
    assert abs(mean(times) - comparison["mean_paired_lap_change_pct"]) < 1e-10
    assert len(times) == comparison["paired_success"]
    assert len(states) == comparison["episodes"]
    for result, pair in (("gained", (False, True)), ("lost", (True, False))):
        assert {k for k, v in states.items() if v == pair} == {tuple(k) for k in comparison[result]}
    return states, mean(times), manifest["changed_total"], source["total_parameters"]


RAW_COLORS = {(True, True): "#d4e6dd", (False, True): "#186359",
              (True, False): "#a03823", (False, False): "#64656a"}
MAP_NAMES = {"BrandsHatch": "Brands Hatch", "MexicoCity": "Mexico City", "MoscowRaceway": "Moscow Raceway",
             "Nuerburgring": "Nürburgring", "SaoPaulo": "São Paulo", "YasMarina": "Yas Marina"}


def state_symbol(ax, x, y, state, w, h):
    ax.add_patch(Rectangle((x-w/2, y-h/2), w, h, facecolor=RAW_COLORS[state], lw=0))
    # Distinct marks and a fixed order retain all four outcomes in monochrome.
    mark = {(True, True): None, (False, True): "+", (True, False): "x", (False, False): "."}[state]
    if mark:
        ax.plot(x, y, marker=mark, color="white", markersize=6.3 if mark != "." else 3,
                markeredgewidth=1.05, linestyle="none")


def raw_figure(lang, states, delta, changed, parameters):
    english = lang == "en"
    title = "Astra edits a pretrained PPO" if english else "Astra modifica i pesi di una PPO"
    fmt = lambda n: f"{n:,}" if english else f"{n:,}".replace(",", ".")
    subtitle = (f"{fmt(changed)} of {fmt(parameters)} checkpoint values changed" if english else
                f"{fmt(changed)} valori modificati su {fmt(parameters)} nel checkpoint")
    cats = (("Both finish", "Gained finishes", "Lost finishes", "Both collide") if english else
            ("Giri riusciti per entrambi", "Giri recuperati", "Giri persi", "Collisioni per entrambi"))
    counts = Counter(states.values())
    totals = len(states)
    old = sum(a for a, _ in states.values())
    new = sum(b for _, b in states.values())
    desc = [subtitle, f"Original PPO → wall_panic_fast. {old}/{totals} → {new}/{totals}"]
    fig = canvas(8.05)
    header(fig, title, subtitle)
    for j, (numbers, text) in enumerate((
        (f"{old} → {new}", "Finishes in 210 starts" if english else "Giri conclusi su 210"),
        (f"{totals-old} → {totals-new}", "Simulator collisions" if english else "Collisioni del simulatore"),
    )):
        x = (.043, .55)[j]
        fig.text(x, .842, numbers, color=INK, weight="bold", fontsize=23)
        fig.text(x, .809, text, color=MUTED, fontsize=12)
        desc.append(numbers + " " + text)
    key = fig.add_axes([.045, .713, .92, .064])
    key.set(xlim=(0, 1), ylim=(0, 1))
    key.axis("off")
    for i, (state, label) in enumerate(zip(RAW_COLORS, cats)):
        x, y = (.018, .568)[i % 2], (.80, .20)[i // 2]
        state_symbol(key, x, y, state, .033, .32)
        key.text(x+.033, y, f"{counts[state]}  {label}", va="center", fontsize=11.2, color=INK)
        desc.append(f"{counts[state]} {label}")
    maps = sorted({k[0] for k in states})
    seeds = sorted({k[1] for k in states})
    ax = fig.add_axes([.35, .139, .60, .541])
    for y, track in enumerate(maps):
        for x, seed in enumerate(seeds):
            state_symbol(ax, x, y, states[track, seed], .91, .83)
    ax.set(xlim=(-.5, len(seeds)-.5), ylim=(len(maps)-.5, -.5))
    ax.set_xticks(range(len(seeds)), range(1, len(seeds)+1))
    ax.set_yticks(range(len(maps)), [MAP_NAMES.get(m, m) for m in maps])
    ax.xaxis.tick_top()
    ax.tick_params(length=0, labelsize=10.8, colors=INK)
    ax.set_facecolor(PAPER)
    for spine in ax.spines.values():
        spine.set_visible(False)
    order = ("Each column is one start per circuit (seeds 40101–41010)." if english else
             "Ogni colonna è una partenza per circuito (seed 40101–41010).")
    fig.text(.043, .103, order, fontsize=10.7, color=MUTED)
    fig.add_artist(plt.Line2D([.043, .955], [.084, .084], transform=fig.transFigure, color=LINE, lw=1))
    paired = counts[True, True]
    footer = (f"Mean lap time change on {paired} paired finishes" if english else
              f"Variazione media del tempo sui {paired} giri appaiati")
    fig.text(.043, .037, percent(delta, lang), fontsize=19, weight="bold", color=COLORS[0])
    fig.text(.26, .043, footer, fontsize=11.2, color=INK)
    save(fig, "raw", lang, title, ". ".join(desc + [order, percent(delta, lang) + " " + footer]))

def read_data():
    audit = json.loads((LOCKED / "verified_four_way.json").read_text())
    reports = {m: json.loads((LOCKED / f"final_{m}.json").read_text()) for m in MODELS}
    outcomes, times = {}, {}
    starts = {}
    for model in MODELS:
        indexed = {(r["map"], r["seed"]): r for r in reports[model]["rows"]}
        poses = {key: row["start"] for key, row in indexed.items()}
        if starts:
            assert poses == starts, "Evaluation starts differ"
        starts = poses
        audited = [r for r in audit["rows"] if r["model"] == model]
        assert len(indexed) == len(audited) == len(reports[model]["rows"]) == 105
        assert {(r["map"], r["seed"]) for r in audited} == set(indexed)
        counts, laps = [0] * 4, {}
        for row in audited:
            key = row["map"], row["seed"]
            raw = indexed[key]
            assert all(raw[k] == row[k] for k in ("success", "collision", "timeout"))
            assert sum(row[k] for k in ("success", "collision", "timeout")) == 1
            assert row["clean"] == (row["success"] and not row["contact_or_overlap_episode"])
            if row["success"]:
                counts[0 if row["clean"] else 1] += 1
                assert raw["seconds"] == row["episode_seconds"]
                laps[key] = raw["seconds"]
            else:
                counts[2 if row["collision"] else 3] += 1
        outcomes[model], times[model] = counts, laps

    keys = sorted(times["candidate"].keys() & times["previous"].keys() & times["ppo"].keys())
    verified = audit["candidate_three_completed"]
    assert keys == sorted((r["map"], r["seed"]) for r in verified["cases"])
    changes = {}
    for model in ("previous", "ppo"):
        changes[model] = [100 * (times["candidate"][k] / times[model][k] - 1) for k in keys]
        assert abs(mean(changes[model]) - verified["mean_change_pct"][f"candidate_vs_{model}"]) < 1e-10
    return outcomes, keys, changes


def canvas(height):
    fig = plt.figure(figsize=(5.75, height), facecolor=PAPER)
    return fig


def header(fig, title, subtitle):
    fig.text(.042, .96, title, va="top", fontsize=19, weight="bold", color=INK)
    fig.text(.044, .96 - .31 / fig.get_figheight(), subtitle, va="top", fontsize=12, color=MUTED)


def save(fig, kind, lang, title, description):
    stream = StringIO()
    fig.savefig(stream, format="svg", metadata={"Date": None})
    plt.close(fig)
    svg = stream.getvalue()
    begin = svg.index("<svg ")
    end = svg.index(">", begin)
    svg = (svg[:end] + f' role="img" lang="{lang}" aria-labelledby="chart-title chart-description">'
           + f'\n<title id="chart-title">{escape(title)}</title>'
           + f'\n<desc id="chart-description">{escape(description)}</desc>'
           + svg[end + 1:])
    (OUT / f"{kind}-{lang}.svg").write_text(svg, encoding="utf-8")


def outcomes_figure(lang, data):
    s = LABELS[lang]
    fig = canvas(4.20)
    header(fig, s["outcomes"], s["out_sub"])
    ax = fig.add_axes([.042, .125, .92, .65])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    # Counts in the four columns use the same visual scale, from zero to 105.
    left, step = .31, .177
    for j, group in enumerate(s["groups"]):
        x = left + 2 * j * step
        ax.text(x + .152, 1.04, group, ha="center", fontsize=11.4, color=MUTED)
        ax.plot([x, x + .305], [1.0, 1.0], lw=1, color=LINE, clip_on=False)
    for j, name in enumerate(s["categories"]):
        ax.text(left + step*j, .911, name, fontsize=11.4, color=COLORS[j], weight="bold")

    desc = [s["out_sub"], ", ".join(s["categories"])]
    for i, (model, name) in enumerate(zip(MODELS, s["models"])):
        y = .74 - i * .218
        ax.text(0, y, name, fontsize=12.3, va="center", color=INK,
                weight="bold" if model == "candidate" else "normal")
        for j, count in enumerate(data[model]):
            x = left + j * step
            ax.text(x, y + .023, str(count), fontsize=16, va="center", color=INK)
            ax.add_patch(Rectangle((x, y - .078), .135, .022, color=LINE, lw=0))
            ax.add_patch(Rectangle((x, y - .078), .135 * count / sum(data[model]), .022,
                                   color=COLORS[j], lw=0))
        desc.append(name + " — " + ", ".join(map(str, data[model])))
    fig.text(.043, .051, s["out_note"], color=MUTED, fontsize=10.9)
    save(fig, "outcomes", lang, s["outcomes"], ". ".join(desc + [s["out_note"]]))


def percent(value, lang):
    number = f"{value:+.2f}".replace("-", "−")
    return (number.replace(".", ",") if lang == "it" else number) + "%"


def pace_figure(lang, keys, changes):
    s = LABELS[lang]
    fig = canvas(6.2)
    header(fig, s["pace"], s["pace_sub"])
    desc = [s["description"], s["zero"]]
    for i, model in enumerate(("previous", "ppo")):
        values = changes[model]
        n = len(values)
        y = (.52, .17)[i]
        color = (COLORS[0], "#24587d")[i]
        ax = fig.add_axes([.157, y, .79, .225], facecolor=PAPER)
        title, avg, mid = s["versus"][i], percent(mean(values), lang), percent(median(values), lang)
        wins = sum(v < 0 for v in values)
        summary = f'{s["mean"]} {avg}  ·  {s["median"]} {mid}  ·  {wins}/{n} {s["faster"]}'
        fig.text(.043, y+.299, title, color=INK, weight="bold", fontsize=14.4)
        fig.text(.043, y+.257, summary, color=color, fontsize=12)
        desc.extend([title, summary])
        ax.set_axisbelow(True)
        ax.grid(axis="y", color=LINE, linewidth=.65)
        ax.axhline(0, color=MUTED, lw=.9)
        ax.set_xlim(-1, n+2)
        # Both panels use the same start order. The vertical scales differ to retain
        # the full observed range and show variation against the edited PPO.
        ax.set_ylim(*((-69, 4) if i == 0 else (-13.5, 5.8)))
        ticks = [-60, -40, -20, 0] if i == 0 else [-10, -5, 0, 5]
        ax.set_yticks(ticks, [f"{t:+d}%".replace("-", "−") if t else "0%" for t in ticks])
        ax.set_xticks([1, 20, 40, 60, n])
        ax.tick_params(axis="x", length=3 if i else 0, color=MUTED, labelbottom=bool(i))
        ax.tick_params(axis="y", length=0)
        ax.tick_params(labelsize=10.7, labelcolor=MUTED)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.spines["bottom"].set_visible(bool(i))
        ax.spines["bottom"].set_color(LINE)
        ax.scatter(range(1, n+1), values, s=14, color=color, lw=0, zorder=3)
        if model == "previous":
            worst = values.index(min(values))
            circuit, seed = keys[worst]
            assert (circuit, seed) == ("Oschersleben", 73404)
            label = f'{s["outlier"]}\n{percent(values[worst], lang)}'
            ax.annotate(label, xy=(worst+1, values[worst]), xytext=(6, -40),
                        arrowprops={"arrowstyle": "-", "lw": .8, "color": MUTED},
                        fontsize=10.7, color=INK, va="center")
            desc.append(label.replace("\n", " "))
    fig.text(.552, .083, s["order"], color=INK, ha="center", fontsize=11.6)
    fig.text(.043, .024, s["zero"], color=MUTED, fontsize=11)
    save(fig, "pace", lang, s["pace"], ". ".join(desc))


if __name__ == "__main__":
    mpl.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": "locked-article",
                         "font.family": ["DejaVu Sans", "Arial", "sans-serif"]})
    OUT.mkdir(parents=True, exist_ok=True)
    counts, starts, relative_times = read_data()
    raw = read_pretrained()
    for language in LABELS:
        raw_figure(language, *raw)
        outcomes_figure(language, counts)
        pace_figure(language, starts, relative_times)
