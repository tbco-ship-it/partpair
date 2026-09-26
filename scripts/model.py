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
TABLE_TIERS = [450, 550, 650, 750, 850, 1000, 1200]


def psu_verdicts(meas: dict, cpu_tdp: int) -> dict:
    """PSU sizes against measured card draw. Sustained load must stay at or under
    80% of the label; a measured 20 ms spike (TPU "spikes") above the label means
    the size only works with an ATX 3.x unit, which is built for short excursions.
    Never go below the reviewer's measured-draw minimum (or the maker's figure when
    the review gives none): 20 ms samples miss shorter spikes."""
    floor = meas["tpu_psu_w"] or meas["vendor_psu_w"] or 0
    sustained = meas["avg_w"] + cpu_tdp + REST_W
    spike = meas["spike_w"] + cpu_tdp + REST_W if meas["spike_kind"] == "spikes" else None
    rows = []
    for t in TABLE_TIERS:
        pct = round(100 * sustained / t)
        if pct > 80 or t < floor:
            v = "no"
        elif spike is not None and spike > t:
            v = "atx3"
        else:
            v = "ok"
        rows.append({"tier": t, "pct": pct, "v": v})
    ok = next((r["tier"] for r in rows if r["v"] == "ok"), None)
    atx3 = next((r["tier"] for r in rows if r["v"] in ("ok", "atx3")), None)
    return {"sustained": sustained, "spike": spike, "rows": rows, "ok": ok, "atx3": atx3, "floor": floor}


def psu_watts(cpu_tdp: int, gpu_tdp: int) -> dict:
    load = cpu_tdp + gpu_tdp + 100  # board, RAM, storage, fans
    target = load * 1.3
    rec = next((t for t in PSU_TIERS if t >= target), PSU_TIERS[-1])
    return {"load": load, "recommended": rec}
