#!/usr/bin/env python3
"""Construiește fișierele CSV/JSON/GeoJSON consumate de frontend."""

from scripts.afdj_core import build_public_data, project_root


if __name__ == "__main__":
    status = build_public_data(project_root())
    print(f"Date publice generate: {status['station_count']} stații, {status['observation_count']} observații, {status['forecast_count']} prognoze")
