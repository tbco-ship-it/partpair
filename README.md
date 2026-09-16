# PCPairs (pcpairs.com)

Static CPU × GPU bottleneck and PSU calculator site.

```
python3 -m venv .venv && .venv/bin/pip install jinja2
.venv/bin/python scripts/build.py --base / --origin https://pcpairs.com
```

Output goes to `dist/`, which is deployed to GitHub Pages by `.github/workflows/pages.yml`.
Data lives in `data/cpus.json` and `data/gpus.json`; scoring in `scripts/model.py` (mirrored in `static/calc.js`).
