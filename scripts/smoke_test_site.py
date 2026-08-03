#!/usr/bin/env python3
"""Smoke test HTTP pentru aplicația statică și fișierele lazy per stație."""

from __future__ import annotations

import json
import threading
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.afdj_core import project_root


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def fetch(base: str, path: str, expected: str | None = None) -> bytes:
    with urllib.request.urlopen(base + path, timeout=8) as response:
        if response.status != 200:
            raise AssertionError(f"{path}: HTTP {response.status}")
        content_type = response.headers.get("Content-Type", "")
        if expected and expected not in content_type:
            raise AssertionError(f"{path}: Content-Type {content_type!r}, așteptat {expected!r}")
        return response.read()


def run_smoke(public_dir: Path) -> dict[str, object]:
    handler = partial(QuietHandler, directory=str(public_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/"
    checked: list[str] = []
    try:
        index = fetch(base, "", "text/html").decode("utf-8")
        checked.append("index.html")
        for path, mime in (
            ("assets/css/app.css", "text/css"), ("assets/js/app.js", "javascript"),
            ("assets/js/charts.js", "javascript"), ("assets/js/map.js", "javascript"),
            ("data/status.json", "application/json"), ("data/latest.geojson", "application/geo+json"),
            ("data/downloads.json", "application/json"),
        ):
            fetch(base, path, mime if path != "data/latest.geojson" else None)
            checked.append(path)
        status = json.loads(fetch(base, "data/status.json"))
        geojson = json.loads(fetch(base, "data/latest.geojson"))
        if status["station_count"] != len(geojson["features"]):
            raise AssertionError("status.station_count diferă de GeoJSON")
        selected = []
        wanted = {"bazias", "giurgiu", "sulina"}
        for feature in geojson["features"]:
            slug = feature["properties"]["slug"]
            if slug in wanted:
                for suffix in ("observations.json", "forecasts.json", "forecast-scores.json"):
                    path = f"data/station/{slug}-{suffix}"
                    json.loads(fetch(base, path))
                    checked.append(path)
                selected.append(slug)
        if set(selected) != wanted:
            raise AssertionError(f"Stații smoke lipsă: {sorted(wanted - set(selected))}")
        for relative in ("./assets/css/app.css", "./assets/js/app.js", "./data/downloads.json"):
            if relative not in index:
                raise AssertionError(f"Resursa relativă pentru GitHub Pages lipsește: {relative}")
        return {"ok": True, "base_url": base, "checked_resources": len(checked), "stations": selected}
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == "__main__":
    print(json.dumps(run_smoke(project_root() / "public"), ensure_ascii=False, indent=2))
