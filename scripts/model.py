"""Shared scoring model for PartPair. Kept tiny and dependency-free so the
same numbers can be mirrored in the browser calculator (static/calc.js)."""
import re

RESOLUTIONS = [
    # key, label, cpu_needed = a + b * gpu.s1440
    ("1080p", "1080p", 45.0, 0.62),
    ("1440p", "1440p", 40.0, 0.60),
    ("4k", "4K", 30.0, 0.50),
]

VERDICT_LABELS = {
    "balanced": "balanced",
    "mild": "mild CPU bottleneck",
    "moderate": "moderate CPU bottleneck",
    "severe": "severe CPU bottleneck",
    "gpu-bound": "GPU-bound (normal)",
    "overkill": "CPU overkill",
}

PSU_TIERS = [450, 550, 650, 750, 850, 1000, 1200, 1600]


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"^(nvidia geforce|amd radeon|amd|intel)\s+", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def short(name: str) -> str:
    """Display name without the vendor prefix (e.g. 'RTX 4070 Super')."""
    return re.sub(r"^(NVIDIA GeForce|AMD Radeon|AMD|Intel)\s+", "", name)


def gpu_res_scores(s1440: float) -> dict:
    f = s1440 / 100.0
    return {
        "1080p": round(100 * f ** 0.85, 1),
        "1440p": round(s1440, 1),
        "4k": round(100 * f ** 1.15, 1),
    }


def bottleneck(cpu_game: float, gpu_s1440: float, res_key: str) -> dict:
    _, label, a, b = next(r for r in RESOLUTIONS if r[0] == res_key)
    needed = a + b * gpu_s1440
    ratio = cpu_game / needed
    if ratio < 1:
        side, pct = "CPU", (1 - ratio) * 100
    else:
        side, pct = "GPU", (1 - 1 / ratio) * 100
    pct = round(pct)
    if side == "CPU":
        verdict = "balanced" if pct <= 10 else "mild" if pct <= 25 else "moderate" if pct <= 40 else "severe"
    else:  # GPU-limited is the healthy direction; only flag a clearly wasted CPU
        verdict = "balanced" if pct <= 20 else "gpu-bound" if pct <= 40 else "overkill"
    verdict_label = VERDICT_LABELS[verdict]
    return {"res": res_key, "label": label, "side": side, "pct": pct,
            "verdict": verdict, "verdict_label": verdict_label, "needed": round(needed)}


REST_W = 75  # motherboard, RAM, storage, fans in a typical gaming load


def psu_pick(meas: dict, cpu_tdp: int) -> dict:
    """PSU sizes from measured card draw (mirrored in static/calc.js).

    A size fits when the sustained gaming load is at most 80% of the label (70% when
    the review has no 20 ms spike data) and, when spikes were measured, the spike
    load stays under the label. "safe" also meets the higher of the card maker's
    and the reviewer's recommendation. "quality" fits the measured draw and meets the
    reviewer's minimum but sits below the maker's higher figure: only for a good unit, and
    only when spikes were measured."""
    sustained = meas["avg_w"] + cpu_tdp + REST_W
    spike = meas["spike_w"] + cpu_tdp + REST_W if meas["spike_kind"] == "spikes" else None
    cap = 0.80 if spike is not None else 0.70
    maker = max(meas["vendor_psu_w"] or 0, meas["tpu_psu_w"] or 0)  # the higher recommendation
    reviewer = meas["tpu_psu_w"] or maker
    rows = []
    for t in PSU_TIERS:
        pct = round(100 * sustained / t)
        fits = sustained <= cap * t and (spike is None or spike <= t)
        if fits and t >= maker:
            v = "safe"
        elif fits and spike is not None and t >= reviewer:
            v = "quality"
        else:
            v = "no"
        rows.append({"tier": t, "pct": pct, "v": v})
    safe = next(r["tier"] for r in rows if r["v"] == "safe")
    quality = next((r["tier"] for r in rows if r["v"] == "quality"), None)
    return {"sustained": sustained, "spike": spike, "rows": rows, "safe": safe, "quality": quality,
            "maker": maker, "cap": round(cap * 100),
            "load": sustained, "recommended": safe}  # load/recommended: names the older templates use
