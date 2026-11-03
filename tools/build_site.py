#!/usr/bin/env python3
"""Build the bilingual static site. Requires Python 3.10+, Node 20+, Marked 17.

Install the build-only Markdown parser with `npm install --global marked@17.0.5`,
then run `python3 tools/build_site.py` from the research repository. An existing
Marked CLI can be supplied via --marked. No client-side scripts or fonts are used.
"""
import argparse
import os
import posixpath
import re
import shutil
import subprocess
from dataclasses import dataclass
from html import escape, unescape
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = "/research/f1tenth-weight-space/"
ORIGIN = "https://tommasopatriti.me"
REPO = "https://github.com/Ro0t-set/f1tenth-weight-space-racing"
UPSTREAM = "https://github.com/zucchero-sintattico/svs-f1tenth_gym"
REV = "9381a13eec6b182ff38e4fba55a105cf94219da6"
PAGES = ("article", *(f"phase{n}" for n in range(1, 7)), "methods")
REPORTS = dict(zip(PAGES[1:7], ("RESULTS.md", "RACING_RESULTS.md", "ULTRA_RESULTS.md",
                                 "TRAJECTORY_RESULTS.md", "FROM_SCRATCH_RESULTS.md",
                                 "ARC_RECOVERY_RESULTS.md")))
LABELS = {
    "it": dict(research="Ricerca", topic="Guida autonoma", article="Articolo", phase="Fase",
               methods="Metodi e dati", index="Indice dello studio", resources="Fonti e materiali",
               report="Report della fase", upstream="Progetto originale", repo="Codice e dati",
               skip="Vai al contenuto", back="Torna all’indice", language="Lingua", date="3 novembre 2026",
               nav=("Articolo", "Modifiche alla PPO", "Velocità e drift", "Correzione dello sterzo",
                    "Contatti e traiettorie", "Rete geometrica", "Velocità e partenze", "Metodi e dati")),
    "en": dict(research="Research", topic="Autonomous driving", article="Article", phase="Phase",
               methods="Methods and data", index="Study contents", resources="Sources and materials",
               report="Phase report", upstream="Original project", repo="Code and data",
               skip="Skip to content", back="Back to the index", language="Language", date="3 November 2026",
               nav=("Article", "Editing the PPO", "Speed and drift", "Steering repair",
                    "Contact and trajectories", "Geometric network", "Pace and starts", "Methods and data")),
}


def page_path(lang, slug):
    return f"{lang}/" if slug == "article" else f"{lang}/{slug}/"


def relative(current, target):
    path = posixpath.relpath(target or ".", current or ".")
    return path + "/" if target.endswith("/") or not target else path


def plain(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", html)).split())


@dataclass
class Page:
    title: str
    byline: str
    intro: str
    body: str
    description: str


def read_page(marked, lang, slug):
    source = ROOT / "sitecontent" / lang / f"{slug}.md"
    html = subprocess.run([marked, "--gfm"], input=source.read_text(encoding="utf-8"),
                          capture_output=True, text=True, check=True).stdout
    match = re.match(r"\s*<h1>(.*?)</h1>\s*", html, re.S)
    if not match:
        raise ValueError(f"{source.name} ({lang}) must begin with an H1 title")
    body = html[match.end():]
    byline = ""
    credit = re.match(r"<p>(Tommaso Patriti · [^<]+)</p>\s*", body)
    if credit:
        byline = plain(credit[1])
        body = body[credit.end():]
    lead = re.match(r"<p>.*?</p>\s*", body, re.S)
    intro = lead.group() if lead else ""
    first_para = re.search(r"<p>(.*?)</p>", body, re.S)
    description = plain(first_para[1] if first_para else match[1])
    if len(description) > 220:
        description = description[:217].rsplit(" ", 1)[0] + "…"
    return Page(plain(match[1]), byline, intro, body[len(intro):], description)


def transform(html, lang, slug, output):
    """Resolve the two Markdown link conventions: site routes and research repo paths."""
    current = page_path(lang, slug)

    def rewrite(match):
        tag, attr, raw = match.groups()
        url = urlsplit(unescape(raw))
        path = unquote(url.path)
        figure_link = tag == "a" and path.startswith("results/article/") and path.endswith(".svg") and not (url.scheme or url.netloc)
        pdf_link = tag == "a" and path.startswith("output/pdf/") and path.endswith(".pdf")
        if tag in ("img", "video", "source") or figure_link or pdf_link:
            if url.scheme or url.netloc or path.startswith("/"):
                raise ValueError(f"{slug} has a non-local image: {raw}")
            src = (ROOT / path).resolve()
            if not src.is_relative_to(ROOT) or not src.is_file():
                raise ValueError(f"{slug} references an unavailable image: {path}")
            target = f"assets/{src.relative_to(ROOT).as_posix()}"
            dest = output / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            if figure_link or pdf_link:
                return f'<a href="{escape(relative(current, target))}"'
            if tag in ("video", "source"):
                return f'<{tag} {attr}="{escape(relative(current, target))}"'
            return f'<img loading="lazy" decoding="async" src="{escape(relative(current, target))}"'

        if url.scheme or url.netloc or not path or path.startswith("/"):
            return match[0]
        file = PurePosixPath(path)
        if file.suffix == ".md" and file.stem in PAGES:
            dest = relative(current, page_path(lang, file.stem))
        elif path.startswith("upstream/"):
            dest = f"{UPSTREAM}/blob/{REV}/{quote(path.removeprefix('upstream/'))}"
        elif (ROOT / path).resolve().is_relative_to(ROOT) and (ROOT / path).exists():
            item = ROOT / path
            kind = "tree" if item.is_dir() else "blob"
            dest = f"{REPO}/{kind}/main/{quote(item.resolve().relative_to(ROOT).as_posix())}"
        elif path.endswith("/") or path in (".", ".."):
            return match[0]  # A relative link to a rendered page.
        else:
            raise ValueError(f"{lang}/{slug} references a missing file: {path}")
        dest = urlunsplit(("", "", dest, url.query, url.fragment))
        return f'<{tag} {attr}="{escape(dest)}"'

    html = re.sub(r'<(img|a|video|source) (src|href)="([^"]+)"', rewrite, html)
    def poster(match):
        path = (ROOT / unescape(match[1])).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"Missing video poster: {path.name}")
        target = f"assets/{path.relative_to(ROOT).as_posix()}"
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        return f'poster="{escape(relative(current, target))}"'
    html = re.sub(r'poster="([^"]+)"', poster, html)
    return html.replace("<table>", '<div class="table-scroll"><table>').replace("</table>", "</table></div>")


def head(lang, current, slug, title, description):
    canonical = ORIGIN + BASE + current
    default = ORIGIN + BASE + (page_path("en", slug) if slug != "article" else "")
    alternates = "\n".join(
        f'<link rel="alternate" hreflang="{code}" href="{ORIGIN + BASE + page_path(code, slug)}">'
        for code in LABELS)
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Tommaso Patriti</title>
<meta name="description" content="{escape(description)}">
<meta name="theme-color" content="#f6f4ef">
<meta property="og:type" content="{'article' if current else 'website'}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{canonical}">
<link rel="canonical" href="{canonical}">
{alternates}
<link rel="alternate" hreflang="x-default" href="{default}">
<link rel="stylesheet" href="{relative(current, 'assets/study.css')}">
</head>"""


def masthead(lang, current, slug):
    text = LABELS[lang]
    languages = []
    for code, name in (("it", "Italiano"), ("en", "English")):
        attrs = ' aria-current="page"' if current and code == lang else ""
        languages.append(f'<a href="{relative(current, page_path(code, slug))}" lang="{code}" '
                         f'hreflang="{code}" aria-label="{name}"{attrs}>{code.upper()}</a>')
    return f"""<a class="skip" href="#content">{text['skip']}</a>
<header class="mast"><div class="wrap mast-row">
<a class="signature" rel="home" href="{ORIGIN}/"><b aria-hidden="true">TP</b> Tommaso Patriti</a>
<nav class="languages" aria-label="{text['language']}">{''.join(languages)}</nav>
</div></header>"""


def study_page(pages, lang, slug, output):
    labels = LABELS[lang]
    index = PAGES.index(slug)
    page = pages[lang, slug]
    current = page_path(lang, slug)
    nav = []
    for i, (item, title) in enumerate(zip(PAGES, labels["nav"])):
        attrs = ' aria-current="page"' if item == slug else ""
        number = f"{i:02}" if 0 < i < 7 else ("§" if i else "↳")
        nav.append(f'<li><a href="{relative(current, page_path(lang, item))}"{attrs}>'
                   f'<span aria-hidden="true">{number}</span>{title}</a></li>')
    report = (f'<a href="{REPO}/blob/main/{REPORTS[slug]}">{labels["report"]}</a>'
              if slug in REPORTS else "")
    section = labels["article"] if not index else (
        f'{labels["phase"]} {index:02} / 06' if slug in REPORTS else labels["methods"])
    credit = escape(page.byline) if page.byline else f'<time datetime="2026-11-03">{labels["date"]}</time>'
    intro = transform(page.intro, lang, slug, output)
    if slug == "article":
        intro = '<h2 class="abstract-label">Abstract</h2>' + intro
    body = transform(page.body, lang, slug, output)
    return f"""{head(lang, current, slug, page.title, page.description)}
<body>{masthead(lang, current, slug)}
<main id="content" class="wrap">
<header class="hero">
<div class="eyeline"><a href="{relative(current, '')}">{labels['research']}</a>
<span>F1TENTH</span><span>{labels['topic']}</span></div>
<div class="folio"><b>{section}</b> <span>{credit}</span></div>
<h1>{escape(page.title)}</h1>
<div class="intro">{intro}</div>
</header>
<div class="reading-grid">
<nav class="study-index" id="study-index" aria-label="{labels['index']}">
<h2>{labels['index']}</h2><ol>{''.join(nav)}</ol></nav>
<article class="prose">{body}
<footer class="sources"><h2>{labels['resources']}</h2><div>{report}
<a href="{REPO}">{labels['repo']}</a>
<a href="{UPSTREAM}/tree/{REV}">{labels['upstream']}</a></div></footer>
</article></div></main>
<footer class="end wrap"><span>Tommaso Patriti · F1TENTH</span>
<a href="#study-index">{labels['back']} ↑</a></footer>
</body></html>
"""


def landing(pages):
    cards = []
    for code, name, action in (("it", "Italiano", "Leggi l’articolo"), ("en", "English", "Read the article")):
        page = pages[code, "article"]
        cards.append(f'<a class="edition" href="{code}/" hreflang="{code}" lang="{code}">'
                     f'<span class="edition-label">{name} / {code.upper()}</span>'
                     f'<strong>{escape(page.title)}</strong><span class="edition-action">{action} →</span></a>')
    return f"""{head("it", "", "article", "F1TENTH · Weight-space programming",
                     "Studio sperimentale sulla guida autonoma in F1TENTH. An experimental study of autonomous driving in F1TENTH.")}
<body>{masthead("it", "", "article")}
<main class="wrap landing" id="content">
<div class="eyeline"><span>Ricerca</span><span lang="en">Research</span></div>
<h1>F1TENTH</h1><p class="subtitle" lang="en">Weight-space programming</p>
<div class="editions">{''.join(cards)}</div>
</main><footer class="end wrap"><span>Tommaso Patriti</span><a href="{REPO}">GitHub ↗</a></footer>
</body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marked", default=os.environ.get("MARKED_BIN", "marked"), help="Path to the Marked CLI")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / BASE.strip("/"),
                        help="Directory to contain the research landing page")
    args = parser.parse_args()
    if not shutil.which(args.marked):
        parser.error("Marked is required. Install marked@17.0.5 or pass its executable with --marked.")
    pages = {(lang, slug): read_page(args.marked, lang, slug) for lang in LABELS for slug in PAGES}
    files = {page_path(lang, slug): study_page(pages, lang, slug, args.output) for lang, slug in pages}
    files[""] = landing(pages)
    for path, html in files.items():
        directory = args.output / path
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "index.html").write_text(html, encoding="utf-8")
    assets = args.output / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("study.css"), assets / "study.css")
    print(f"Built {len(files)} pages in {args.output}")


if __name__ == "__main__":
    main()
