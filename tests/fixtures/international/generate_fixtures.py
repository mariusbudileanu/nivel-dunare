"""Generate compact, deterministic parser-contract fixtures (not live samples)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
CAPTURED = "2026-08-04T10:00:00+00:00"


def save(source: str, payloads: list[tuple[str, str, str, str]]) -> None:
    folder = ROOT / source
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {"captured_at_utc": CAPTURED, "payloads": []}
    for label, filename, content_type, body in payloads:
        (folder / filename).write_text(body, encoding="utf-8")
        manifest["payloads"].append({
            "label": label, "file": filename, "url": f"https://fixture.invalid/{source}/{filename}",
            "content_type": content_type,
        })
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def de() -> None:
    rows = []
    for index in range(18):
        rows.append({
            "uuid": f"de-{index:02d}", "longname": f"Donau Station {index:02d}",
            "agency": "WSV", "water": {"shortname": "DONAU"}, "km": 2300 - index * 10,
            "latitude": 48.1 + index * 0.02, "longitude": 9.8 + index * 0.15,
            "timeseries": [{"shortname": "W", "unit": "cm", "currentMeasurement": {
                "value": 200 + index, "timestamp": "2026-08-04T10:00:00+02:00"}}],
        })
    rows[-1].pop("latitude")
    rows[-1].pop("longitude")
    for index in range(9):
        rows.append({
            "uuid": f"at-republished-{index}", "longname": f"Austria {index}",
            "agency": "VIA DONAU", "water": {"shortname": "DONAU"}, "timeseries": [],
        })
    save("de", [("stations", "stations.json", "application/json", json.dumps(rows))])


def at() -> None:
    names = ["Kienstock", "Krems", "Tulln", "Korneuburg", "Wildungsmauer", "Hainburg", "Linz", "Melk", "Ybbs", "Schwedenbrücke"]
    gauges = [{
        "objectID": f"AT{i:02d}", "objectName": name, "latitude": 48.1 + i * 0.03,
        "longitude": 14.0 + i * 0.15, "riverKm": 2200 - i * 20,
    } for i, name in enumerate(names)]
    millis = 1785830400000
    statuses = [{"currentMeasure": {
        "objectID": item["objectID"], "objectName": item["objectName"], "value": 150 + i,
        "difference": i - 4, "measureDate": millis, "fullHour": True,
    }, "history": [[millis - 3600000, 149 + i]], "forecast": [[millis + 86400000, 151 + i, 145 + i, 157 + i]] if i == 0 else []}
        for i, item in enumerate(gauges)]
    save("at", [
        ("gauge-list", "list.json", "application/json", json.dumps({"gaugeList": gauges}, ensure_ascii=False)),
        ("gauge-status", "status.json", "application/json", json.dumps({"lastUpdated": millis, "gaugeStatusList": statuses}, ensure_ascii=False)),
    ])


def sk() -> None:
    names = ["Devín", "Bratislava", "Gabčíkovo", "Medveďov", "Komárno", "Štúrovo", "Chľaba", "Iža", "Radvaň", "Moča", "Patince", "Dobrohošť", "Sap"]
    options = "".join(f'<option value="{5140+i}">{name} - Dunaj</option>' for i, name in enumerate(names))
    payloads = []
    for i, name in enumerate(names):
        body = f'''<!doctype html><html><body><select>{options}</select>
<table><caption>Merané hodnoty</caption><tr><th>time</th><th>level</th><th>temp</th></tr>
<tr><td>04.08.2026 10:00</td><td>{200+i}</td><td>{20+i/10:.1f}</td></tr></table>
<script>var forecast_serie = {{ data: [[1785916800000,{201+i}],[1786003200000,{202+i}]] }};</script>
</body></html>'''
        payloads.append((f"station-{5140+i}", f"station-{5140+i}.html", "text/html; charset=utf-8", body))
    save("sk", payloads)


def hu() -> None:
    primary_names = ["Rajka", "Dunaremete", "Nagybajcs", "Gönyű", "Komárom", "Esztergom", "Nagymaros", "Vác", "Budapest", "Adony", "Dunaújváros", "Dunaföldvár", "Paks", "Dombori", "Baja", "Mohács", "Hercegszántó", "Fajsz", "Szentendre", "Ercsi", "Százhalombatta", "Solt", "Madocsa", "Gerjen", "Báta"]
    rows = []
    for i, name in enumerate(primary_names):
        rows.append(f"<tr><td>4{i:03d}</td><td>{name}</td><td>Duna</td><td>x</td><td>x</td><td>{100+i}</td><td>{i-12}</td><td>{1000+i}</td><td>{22+i/10:.1f}</td><td>x</td></tr>")
    for i in range(68):
        rows.append(f"<tr><td>{5+i//10}{i:03d}</td><td>Foreign {i}</td><td>Duna</td><td>x</td><td>x</td><td>{200+i}</td><td>0</td><td></td><td></td><td>x</td></tr>")
    current = "<!doctype html><html><body><h1>2026. augusztus 4.</h1><table>" + "".join(rows) + "</table></body></html>"
    forecast = "<!doctype html><html><body>Water level forecast for next six days. Narrative only.</body></html>"
    save("hu", [("current", "current.html", "text/html; charset=utf-8", current), ("forecast-narrative", "forecast.html", "text/html; charset=utf-8", forecast)])


def hr() -> None:
    document = {}
    for i, key in enumerate(("aljmas", "batina", "vukovar")):
        document[key] = [{"datum": "04.08.2026", "vodostaj": str(50 + i)}, {"datum": "03.08.2026", "vodostaj": str(49 + i)}]
    save("hr", [("current", "current.json", "application/json", json.dumps(document))])


def bg() -> None:
    main_names = ["Novo Selo", "Vidin", "Lom", "Oryahovo", "Nikopol", "Svishtov", "Ruse", "Silistra"]
    auto_names = ["Novo Selo", "Gomotartsi", "Lom", "Kozloduj", "Oryahovo", "Bajkal", "Nikopol", "Svishtov", "Ruse", "Ryahovo", "Malak Preslavets", "Силистра"]
    main = "".join(f"<tr><td>{name}</td><td>{833.6-i*50:.1f}</td><td>{-60+i}</td><td>{1500+i}</td><td>{i-4}</td><td>{26+i/10:.1f}</td></tr>" for i, name in enumerate(main_names))
    directions = ["down", "down", "nochange", "down", "down", "nochange", "down", "nochange", "nochange", "nochange", "nochange", "up"]
    automatic = "".join(f'<tr><td>{name}</td><td>{833.6-i*38:.1f}</td><td>{-180+i}</td><td><img src="images/nav/{directions[i]}.gif"></td><td>{26+i/10:.1f}</td></tr>' for i, name in enumerate(auto_names))
    current = f'''<!doctype html><html><body><h3>Water levels on the bulgarian section of the Danube river 04.08.2026</h3>
<table><tr><td>station</td><td>kilometre</td><td>water level (cm)</td><td>discharge (m3/s)</td><td>24 hours difference (cm)</td><td>t water</td></tr>{main}</table>
<table><tr><td>station</td><td>kilometre</td><td>water level [cm]</td><td>last 6 hours difference</td><td>t water</td></tr>{automatic}</table></body></html>'''
    forecast_names = ["Oryahovo", "Nikopol", "Svishtov", "Ruse", "Silistra"]
    blocks = []
    for i, name in enumerate(forecast_names):
        days = "".join(f"<td>{day:02d}.08</td>" for day in range(5, 11))
        maximum = "".join(f"<td>{-20+i-day}</td>" for day in range(6))
        central = "".join(f"<td>{-25+i-day}</td>" for day in range(6))
        minimum = "".join(f"<td>{-30+i-day}</td>" for day in range(6))
        blocks.append(f'''<h3>{name}</h3><canvas></canvas><table><tr><td>day</td>{days}</tr><tr><td>max</td>{maximum}</tr><tr><td>forecast</td>{central}</tr><tr><td>min</td>{minimum}</tr></table>''')
    forecast = "<!doctype html><html><body>" + "".join(blocks) + "</body></html>"
    save("bg", [("current", "current.html", "text/html; charset=utf-8", current), ("forecast", "forecast.html", "text/html; charset=utf-8", forecast)])


if __name__ == "__main__":
    de(); at(); sk(); hu(); hr(); bg()
