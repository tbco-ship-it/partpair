#!/usr/bin/env python3
"""Generate the static PartPair site into dist/.

Usage: build.py [--base /partpair/] [--origin https://example.com]
"""
import argparse
import json
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from model import RESOLUTIONS, bottleneck, gpu_res_scores, psu_watts, short, slugify

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SITE = "PartPair"


def load():
    cpus = json.loads((ROOT / "data/cpus.json").read_text())
    gpus = json.loads((ROOT / "data/gpus.json").read_text())
    for c in cpus:
        c["slug"] = slugify(c["name"])
        c["short"] = short(c["name"])
    for g in gpus:
        g["slug"] = slugify(g["name"])
        g["short"] = short(g["name"])
        g["scores"] = gpu_res_scores(g["s1440"])
    cpus.sort(key=lambda c: -c["game"])
    gpus.sort(key=lambda g: -g["s1440"])
    return cpus, gpus


def combo(cpu, gpu):
    results = [bottleneck(cpu["game"], gpu["s1440"], r[0]) for r in RESOLUTIONS]
    return {
        "cpu": cpu, "gpu": gpu, "results": results,
        "main": results[1],  # 1440p is the headline
        "psu": psu_watts(cpu["tdp"], gpu["tdp"]),
        "path": f"bottleneck/{cpu['slug']}-vs-{gpu['slug']}/",
    }


def suggest_cpus(cpu, gpu, cpus):
    """CPUs on the same socket that remove the 1440p CPU bottleneck."""
    needed = bottleneck(cpu["game"], gpu["s1440"], "1440p")["needed"]
    pool = [c for c in cpus if c["socket"] == cpu["socket"] and c["game"] >= needed and c["slug"] != cpu["slug"]]
    pool.sort(key=lambda c: c["game"])
    return pool[:3]


def suggest_gpus(cpu, gpu, gpus):
    """GPUs that would use this CPU more fully (closest 1440p match above current)."""
    cap = (cpu["game"] - 40.0) / 0.60  # invert cpu_needed at 1440p
    pool = [g for g in gpus if gpu["s1440"] < g["s1440"] <= cap + 8 and g["slug"] != gpu["slug"]]
    pool.sort(key=lambda g: abs(g["s1440"] - cap))
    return pool[:3]


def neighbours(items, item, n=4):
    i = items.index(item)
    lo = max(0, i - n // 2)
    return [x for x in items[lo:lo + n + 1] if x is not item][:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/")
    ap.add_argument("--origin", default="https://tbco-ship-it.github.io")
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    origin = args.origin.rstrip("/")

    cpus, gpus = load()
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.globals.update(site=SITE, base=base, origin=origin, today=date.today().isoformat(),
                       resolutions=RESOLUTIONS, cpus=cpus, gpus=gpus)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(ROOT / "static", DIST / "static")

    urls = []

    def write(path, template, **ctx):
        out = DIST / path
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(env.get_template(template).render(path=path, **ctx))
        urls.append(path)

    # Data blob for the browser calculator
    blob = {
        "cpus": [{"slug": c["slug"], "name": c["name"], "game": c["game"], "tdp": c["tdp"], "socket": c["socket"]} for c in cpus],
        "gpus": [{"slug": g["slug"], "name": g["name"], "s1440": g["s1440"], "tdp": g["tdp"]} for g in gpus],
    }
    (DIST / "static/parts.json").write_text(json.dumps(blob, separators=(",", ":")))

    write("", "index.html")
    write("psu-calculator/", "psu.html")
    for page in ("about", "methodology", "privacy", "contact"):
        write(f"{page}/", f"{page}.html")

    # Hub pages
    write("cpu/", "cpu_index.html")
    write("gpu/", "gpu_index.html")
    for c in cpus:
        pairs = [combo(c, g) for g in gpus]
        best = sorted(pairs, key=lambda p: p["main"]["pct"])[:6]
        write(f"cpu/{c['slug']}/", "cpu.html", cpu=c, pairs=pairs, best=best)
    for g in gpus:
        pairs = [combo(c, g) for c in cpus]
        best = sorted(pairs, key=lambda p: p["main"]["pct"])[:6]
        write(f"gpu/{g['slug']}/", "gpu.html", gpu=g, pairs=pairs, best=best)

    # Combo pages
    for c in cpus:
        for g in gpus:
            p = combo(c, g)
            write(p["path"], "combo.html", p=p,
                  up_cpus=suggest_cpus(c, g, cpus), up_gpus=suggest_gpus(c, g, gpus),
                  near_gpus=neighbours(gpus, g), near_cpus=neighbours(cpus, c))

    # Sitemap, robots, 404
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"<url><loc>{origin}{base}{u}</loc><lastmod>{date.today().isoformat()}</lastmod></url>")
    sm.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sm))
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {origin}{base}sitemap.xml\n")
    (DIST / "404.html").write_text(env.get_template("404.html").render(path="404"))
    (DIST / ".nojekyll").write_text("")
    print(f"built {len(urls)} pages -> {DIST}")


if __name__ == "__main__":
    main()
