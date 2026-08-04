#!/usr/bin/env python3
"""Smoke test HTTP pentru aplicația statică și fișierele lazy per stație."""

from __future__ import annotations

import argparse
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


def check_base(base: str) -> dict[str, object]:
    base = base.rstrip("/") + "/"
    checked: list[str] = []
    index = fetch(base, "", "text/html").decode("utf-8")
    checked.append("index.html")
    for path, mime in (
        ("assets/css/app.css", "text/css"), ("assets/js/app.js", "javascript"),
        ("assets/js/charts.js", "javascript"), ("assets/js/map.js", "javascript"),
        ("assets/js/i18n.js", "javascript"), ("assets/js/international.js", "javascript"),
        ("assets/js/map-beta.js", "javascript"), ("assets/js/beta-ui.js", "javascript"),
        ("data/status.json", "application/json"), ("data/latest.geojson", None),
        ("data/downloads.json", "application/json"),
    ):
        fetch(base, path, mime)
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
    international_names = (
        "stations.json", "observations.json", "latest.json", "forecasts.json", "sources.json",
        "status.json", "stations.geojson", "unmapped_stations.json", "quality_issues.json",
    )
    international = {}
    for name in international_names:
        path = f"data/international/{name}"
        international[name] = json.loads(fetch(base, path, None if name.endswith(".geojson") else "application/json"))
        checked.append(path)
    international_status = international["status.json"]
    if international_status["station_count"] != 101:
        raise AssertionError("Registrul internațional public nu are 101 stații")
    if len(international["stations.geojson"]["features"]) != 26:
        raise AssertionError("GeoJSON internațional nu are 26 stații cu coordonate verificate")
    if len(international["unmapped_stations.json"]) != 75:
        raise AssertionError("Lista internațională necartografiată nu are 75 stații")
    for language in ("ro", "en"):
        localized_index = fetch(base, f"?lang={language}", "text/html").decode("utf-8")
        if 'id="language-button"' not in localized_index or 'assets/js/app.js' not in localized_index:
            raise AssertionError(f"Interfața {language} nu include mecanismul bilingv")
        checked.append(f"?lang={language}")
    for relative in ("./assets/css/app.css", "./assets/js/app.js", "./data/downloads.json"):
        if relative not in index:
            raise AssertionError(f"Resursa relativă pentru GitHub Pages lipsește: {relative}")
    return {
        "ok": True,
        "base_url": base,
        "checked_resources": len(checked),
        "stations": selected,
        "languages": ["ro", "en"],
        "international": {
            "stations": international_status["station_count"],
            "mapped": international_status["mapped_station_count"],
            "unmapped": international_status["unmapped_station_count"],
        },
    }


def run_smoke(public_dir: Path) -> dict[str, object]:
    handler = partial(QuietHandler, directory=str(public_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return check_base(f"http://127.0.0.1:{server.server_port}/")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="URL public, inclusiv subpath-ul GitHub Pages")
    args = parser.parse_args()
    result = check_base(args.base_url) if args.base_url else run_smoke(project_root() / "public")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())