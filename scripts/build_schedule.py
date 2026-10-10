"""Build site/schedule.json: today's NJ Transit trains between Metuchen and NY Penn.

Reads an NJ Transit rail GTFS zip (path given as argv[1]) and writes the
departure/arrival times for both directions for today's date in New York.
"""
import csv
import io
import json
import sys
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
METUCHEN = "METUCHEN"
PENN = "NEW YORK PENN STATION"


def station(name):
    # NJ Transit's stop names vary ("NEW YORK PENN STATION", "NY PENN STA", ...).
    name = name.strip().upper()
    if name == METUCHEN:
        return METUCHEN
    if "PENN" in name and ("NEW YORK" in name or name.startswith(("NY", "N.Y"))):
        return PENN
    return None


def rows(zf, name):
    if name not in zf.namelist():
        return []
    with zf.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")))


def active_services(zf, day):
    ymd = day.strftime("%Y%m%d")
    weekday = day.strftime("%A").lower()
    services = {
        r["service_id"]
        for r in rows(zf, "calendar.txt")
        if r["start_date"] <= ymd <= r["end_date"] and r[weekday] == "1"
    }
    for r in rows(zf, "calendar_dates.txt"):
        if r["date"] == ymd:
            if r["exception_type"] == "1":
                services.add(r["service_id"])
            else:
                services.discard(r["service_id"])
    return services


def fmt(gtfs_time):
    # GTFS times can exceed 24:00 for trains running past midnight.
    h, m, _ = (int(x) for x in gtfs_time.split(":"))
    h %= 24
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def secs(gtfs_time):
    h, m, sec = (int(x) for x in gtfs_time.split(":"))
    return h * 3600 + m * 60 + sec


def build(gtfs_path, now):
    with zipfile.ZipFile(gtfs_path) as zf:
        stop_ids = {}
        stops = rows(zf, "stops.txt")
        for r in stops:
            if name := station(r["stop_name"]):
                stop_ids[r["stop_id"]] = name
        if set(stop_ids.values()) != {METUCHEN, PENN}:
            penn_like = [r["stop_name"] for r in stops if "PENN" in r["stop_name"].upper()]
            sys.exit(f"Could not find both stations in stops.txt: {stop_ids}; names with PENN: {penn_like}")

        services = active_services(zf, now.date())
        trips = {r["trip_id"]: r for r in rows(zf, "trips.txt") if r["service_id"] in services}

        stops_by_trip = {}
        for r in rows(zf, "stop_times.txt"):
            if r["trip_id"] in trips and r["stop_id"] in stop_ids:
                stops_by_trip.setdefault(r["trip_id"], {})[stop_ids[r["stop_id"]]] = r

    directions = {"to_penn": [], "to_metuchen": []}
    for trip_id, s in stops_by_trip.items():
        if len(s) != 2:
            continue
        m, p = s[METUCHEN], s[PENN]
        if int(m["stop_sequence"]) < int(p["stop_sequence"]):
            key, dep, arr = "to_penn", m, p
        else:
            key, dep, arr = "to_metuchen", p, m
        directions[key].append({
            "sort": dep["departure_time"].zfill(8),
            "depart": fmt(dep["departure_time"]),
            "arrive": fmt(arr["arrival_time"]),
            "dep_min": secs(dep["departure_time"]) // 60,
            "minutes": (secs(arr["arrival_time"]) - secs(dep["departure_time"])) // 60,
            "train": trips[trip_id].get("trip_short_name", ""),
        })

    for trains in directions.values():
        trains.sort(key=lambda t: t["sort"])
        # Flag trains noticeably quicker than the typical one (e.g. express runs).
        typical = sorted(t["minutes"] for t in trains)[len(trains) // 2] if trains else 0
        for t in trains:
            del t["sort"]
            t["fast"] = t["minutes"] <= typical - 5
    return {"date": now.strftime("%A, %B %-d, %Y"), "generated": now.isoformat(), **directions}


if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else "site/schedule.json"
    data = build(sys.argv[1], datetime.now(TZ))
    with open(out, "w") as f:
        json.dump(data, f, indent=1)
    print(f"{len(data['to_penn'])} trains to Penn, {len(data['to_metuchen'])} to Metuchen")
