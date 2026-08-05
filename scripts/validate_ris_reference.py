"""Validate normalized Croatian and Bulgarian RIS gauge registries."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from scripts.sources.reference import ris_rows

EXPECTED_HASHES = {
    "hr-ris_index-v1_7.xls": "3ef66a6ad4d7c35c6cab601dee93cb4bddc8f71a953b682b0f48f9117eea31f1",
    "RIS_Index_BG_01.07.2021_v2p1.xlsx": "0824b69d3bb8deb042514b4fa5e7bfb2bf5b36eebd3cf0e654ad20de4fc3c4d4",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(workbook_dir: Path | None = None) -> dict[str, object]:
    rows = list(ris_rows())
    if len(rows) != 23:
        raise ValueError(f"Expected 23 RIS stream rows, found {len(rows)}")
    countries = Counter(row["country_code"] for row in rows)
    if countries != {"BG": 20, "HR": 3}:
        raise ValueError(f"Unexpected RIS country distribution: {dict(countries)}")
    if any(row["function"] != "wtwgag" for row in rows):
        raise ValueError("Every normalized row must be a RIS wtwgag gauge")
    if any(row["source_crs"] != "EPSG:4326" for row in rows):
        raise ValueError("RIS coordinates must retain the workbook WGS84 CRS declaration")
    if any(row["coordinate_method"] != "official_station_coordinate" for row in rows):
        raise ValueError("RIS coordinates must be official_station_coordinate")
    if len({row["station_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate application station_id in RIS registry")
    bg = [row for row in rows if row["country_code"] == "BG"]
    if len({row["physical_station_id"] for row in bg}) != 13:
        raise ValueError("Expected 13 Bulgarian physical placements for 20 streams")
    if Counter(row["source_stream_type"] for row in bg) != {"automatic": 12, "manual": 8}:
        raise ValueError("Expected 12 automatic and 8 manual Bulgarian streams")
    nikopol = [row for row in bg if row["physical_station_id"] == "bg-nikopol"]
    if len(nikopol) != 2 or len({row["source_station_id"] for row in nikopol}) != 1:
        raise ValueError("Nikopol must reuse the single workbook-proven RIS object across two streams")
    for row in rows:
        expected_hash = EXPECTED_HASHES[row["workbook_filename"]]
        if row["workbook_sha256"] != expected_hash:
            raise ValueError(f"Workbook SHA mismatch in registry row {row['station_id']}")
        if not (-90 <= row["latitude"] <= 90 and -180 <= row["longitude"] <= 180):
            raise ValueError(f"Invalid coordinate for {row['station_id']}")
    checked_workbooks: list[str] = []
    if workbook_dir:
        for filename, expected in EXPECTED_HASHES.items():
            path = workbook_dir / filename
            if not path.is_file():
                raise FileNotFoundError(path)
            actual = sha256(path)
            if actual != expected:
                raise ValueError(f"Original workbook hash mismatch for {filename}: {actual}")
            checked_workbooks.append(filename)
    return {
        "status": "ok",
        "rows": len(rows),
        "countries": dict(countries),
        "bg_physical_placements": len({row["physical_station_id"] for row in bg}),
        "original_workbooks_checked": checked_workbooks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook-dir", type=Path)
    args = parser.parse_args(argv)
    print(validate(args.workbook_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
