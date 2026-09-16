#!/usr/bin/env python3
"""Generate the static PartPair site into dist/.

Usage: build.py [--base /partpair/] [--origin https://example.com]
"""
import argparse
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from model import RESOLUTIONS, bottleneck, gpu_res_scores, psu_watts, short, slugify

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SITE = "PCPairs"


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
    ap.add_argument("--origin", default="https://pcpairs.com")
    ap.add_argument("--cname", default="pcpairs.com")
    ap.add_argument("--adsense-pub", default="pub-8425563704095379", help="AdSense publisher id, e.g. pub-1234567890123456")
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    origin = args.origin.rstrip("/")

    cpus, gpus = load()
    # Content hash of static assets → cache-busting query on every asset URL.
    h = hashlib.md5()
    for f in sorted((ROOT / "static").glob("*")):
        h.update(f.read_bytes())
    asset_v = h.hexdigest()[:8]
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.globals.update(site=SITE, base=base, origin=origin, today=date.today().isoformat(), adsense_pub=args.adsense_pub, v=asset_v,
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

    # Intent pages: best CPU for GPU, best GPU for CPU, PSU requirements per GPU
    def cpu_needed(g, res):
        return bottleneck(0, g["s1440"], res)["needed"]

    for g in gpus:
        pairs = [combo(c, g) for c in cpus]
        n1440, n1080 = cpu_needed(g, "1440p"), cpu_needed(g, "1080p")
        # sweet spot: no CPU bottleneck at 1440p, least wasted CPU first
        ok = [p for p in pairs if not (p["main"]["side"] == "CPU" and p["main"]["pct"] > 10)]
        top = sorted(ok, key=lambda p: p["main"]["pct"])[:10]
        worst = sorted([p for p in pairs if p["main"]["side"] == "CPU" and p["main"]["pct"] > 25], key=lambda p: -p["main"]["pct"])[:5]
        floor = {}
        for c in sorted(cpus, key=lambda c: c["game"]):
            if c["game"] >= n1440 * 0.9 and c["socket"] not in floor:
                floor[c["socket"]] = c
        write(f"best-cpu-for/{g['slug']}/", "best_cpu.html", gpu=g, top=top, worst=worst, floor=floor,
              needed1440=n1440, needed1080=n1080)
        by_tdp = sorted(cpus, key=lambda c: c["tdp"])
        lowc = next(c for c in by_tdp if c["tdp"] <= 65 and c["year"] >= 2022)
        midc = next(c for c in by_tdp if 120 <= c["tdp"] <= 181 and c["year"] >= 2022)
        highc = next(c for c in reversed(by_tdp) if c["tdp"] >= 250)
        write(f"psu-for/{g['slug']}/", "psu_for.html", gpu=g, lowc=lowc, midc=midc, highc=highc,
              low=psu_watts(lowc["tdp"], g["tdp"]), mid=psu_watts(midc["tdp"], g["tdp"]), high=psu_watts(highc["tdp"], g["tdp"]))

    for c in cpus:
        pairs = [combo(c, g) for g in gpus]
        cap = round((c["game"] - 40.0) / 0.60)
        cap1080 = round((c["game"] - 45.0) / 0.62)
        cap4k = round((c["game"] - 30.0) / 0.50)
        ok = [p for p in pairs if not (p["main"]["side"] == "CPU" and p["main"]["pct"] > 10)]
        top = sorted(ok, key=lambda p: p["main"]["pct"])[:10]
        over = sorted([p for p in pairs if p["main"]["side"] == "CPU" and p["main"]["pct"] > 10], key=lambda p: p["main"]["pct"])[:6]
        under = sorted([p for p in pairs if p["main"]["side"] == "GPU" and p["main"]["pct"] > 40], key=lambda p: -p["main"]["pct"])[:6]
        write(f"best-gpu-for/{c['slug']}/", "best_gpu.html", cpu=c, top=top, over=over, under=under,
              cap=cap, cap1080=cap1080, cap4k=cap4k)

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
    for f in (ROOT / "static").glob("naver*.html"):  # Naver Search Advisor ownership file at site root
        shutil.copy(f, DIST / f.name)
    key = (ROOT / "static/indexnow-key.txt").read_text().strip()
    (DIST / f"{key}.txt").write_text(key + "\n")
    if args.adsense_pub:
        (DIST / "ads.txt").write_text(f"google.com, {args.adsense_pub}, DIRECT, f08c47fec0942fa0\n")
    if args.cname:
        (DIST / "CNAME").write_text(args.cname + "\n")
    print(f"built {len(urls)} pages -> {DIST}")


if __name__ == "__main__":
    main()
