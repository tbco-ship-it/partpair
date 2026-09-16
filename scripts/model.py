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


def psu_watts(cpu_tdp: int, gpu_tdp: int) -> dict:
    load = cpu_tdp + gpu_tdp + 100  # board, RAM, storage, fans
    target = load * 1.3
    rec = next((t for t in PSU_TIERS if t >= target), PSU_TIERS[-1])
    return {"load": load, "recommended": rec}
