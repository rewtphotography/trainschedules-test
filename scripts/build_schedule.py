"""Build site/schedule.json: today's NJ Transit rail trips, for any station pair.

Reads an NJ Transit rail GTFS zip (path given as argv[1]) and writes every trip
running today (New York time) as its ordered list of station stops. The page
picks out trains between whichever two stations the viewer has chosen.
"""
import csv
import io
import json
import sys
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
PENN = "New York Penn Station"
KEEP_UPPER = {"NJ", "NY", "NYC", "PATH", "II", "III", "MSU"}


def station(name):
    # NJ Transit's stop names vary ("NEW YORK PENN STATION", "NY PENN STA", ...).
    upper = name.strip().upper()
    if "PENN" in upper and ("NEW YORK" in upper or upper.startswith(("NY", "N.Y"))):
        return PENN
    return " ".join(w if w in KEEP_UPPER else w.capitalize() for w in upper.split())


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


def minutes(gtfs_time):
    # GTFS times can exceed 24:00 for trains running past midnight.
    h, m, _ = (int(x) for x in gtfs_time.split(":"))
    return h * 60 + m


def build(gtfs_path, now):
    with zipfile.ZipFile(gtfs_path) as zf:
        stop_station = {r["stop_id"]: station(r["stop_name"]) for r in rows(zf, "stops.txt")}
        services = active_services(zf, now.date())
        trips = {r["trip_id"]: r for r in rows(zf, "trips.txt") if r["service_id"] in services}

        stops_by_trip = {}
        for r in rows(zf, "stop_times.txt"):
            if r["trip_id"] in trips and r["stop_id"] in stop_station:
                stops_by_trip.setdefault(r["trip_id"], []).append(r)

    names = sorted({stop_station[r["stop_id"]] for stops in stops_by_trip.values() for r in stops})
    index = {n: i for i, n in enumerate(names)}

    out_trips = []
    for trip_id, stops in stops_by_trip.items():
        stops.sort(key=lambda r: int(r["stop_sequence"]))
        out_trips.append([
            trips[trip_id].get("trip_short_name", ""),
            [[index[stop_station[r["stop_id"]]], minutes(r["arrival_time"]), minutes(r["departure_time"])]
             for r in stops],
        ])
    out_trips.sort(key=lambda t: t[1][0][2])

    return {
        "date": now.strftime("%A, %B %-d, %Y"),
        "generated": now.isoformat(),
        "stations": names,
        # Each trip: [train number, [[station index, arrive minute, depart minute], ...]]
        "trips": out_trips,
    }


if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else "site/schedule.json"
    data = build(sys.argv[1], datetime.now(TZ))
    for required in ("Metuchen", PENN):
        if required not in data["stations"]:
            penn_like = [s for s in data["stations"] if "Penn" in s]
            sys.exit(f"{required!r} not found in today's stations; names with Penn: {penn_like}")
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{len(data['trips'])} trips across {len(data['stations'])} stations")
