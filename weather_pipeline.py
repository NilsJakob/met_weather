import requests
import pandas as pd
from datetime import datetime, timedelta
from datetime import datetime, UTC
import os
from dotenv import load_dotenv

# ======================
# LOAD ENV
# ======================


load_dotenv()

FROST_CLIENT_ID = os.getenv("FROST_CLIENT_ID")

if not FROST_CLIENT_ID:
    raise ValueError("❌ Missing FROST_CLIENT_ID (check .env locally or GitHub Secrets)")



test_url = "https://frost.met.no/sources/v0.jsonld"

r = requests.get(test_url, auth=(FROST_CLIENT_ID, ""))

print("TEST STATUS:", r.status_code)
print("TEST RESPONSE:", r.text[:200])

if not FROST_CLIENT_ID:
    raise ValueError("❌ Missing FROST_CLIENT_ID in .env")

# ======================
# CONFIG
# ======================

LAT = 59.137344
LON = 9.671435

DEFAULT_STATION = "SN17850"

FORECAST_FILE = "forecast.csv"
OBS_FILE = "observations.csv"

# ======================
# FORECAST (MET)
# ======================

def get_forecast():
    print("🔄 Fetching forecast...")

    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LAT}&lon={LON}"
    headers = {"User-Agent": "weather-pipeline"}

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        raise Exception(f"Forecast error: {r.status_code}")

    data = r.json()

    rows = []

    for ts in data["properties"]["timeseries"]:
        details = ts["data"]["instant"]["details"]

        rows.append({
            "time_utc": ts["time"],
            "temperature_fc": details.get("air_temperature"),
            "wind_fc": details.get("wind_speed"),
        })

    df = pd.DataFrame(rows)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)

    print("✅ Forecast rows:", len(df))
    return df


# ======================
# STATION LOGIC
# ======================

def get_nearest_station_raw():
    url = "https://frost.met.no/sources/v0.jsonld"

    params = {
        "geometry": f"nearest(POINT({LON} {LAT}))",
        "nearestmaxcount": 1
    }

    r = requests.get(url, params=params, auth=(FROST_CLIENT_ID, ""))

    if r.status_code != 200:
        raise Exception("Station lookup failed")

    data = r.json()
    return data["data"][0]["id"]


def has_recent_data(station_id):
    url = "https://frost.met.no/observations/v0.jsonld"

    end = datetime.now(UTC)
    start = end - timedelta(hours=6)

    params = {
        "sources": station_id,
        "elements": "air_temperature",
        "referencetime": f"{start.isoformat()}/{end.isoformat()}"
    }

    r = requests.get(url, params=params, auth=(FROST_CLIENT_ID, ""))

    if r.status_code != 200:
        return False

    data = r.json()
    return len(data.get("data", [])) > 0


def get_nearest_station_with_data():
    url = "https://frost.met.no/sources/v0.jsonld"

    params = {
        "geometry": f"nearest(POINT({LON} {LAT}))",
        "elements": "air_temperature",
        "nearestmaxcount": 1
    }

    r = requests.get(url, params=params, auth=(FROST_CLIENT_ID, ""))

    if r.status_code != 200:
        raise Exception("Fallback station lookup failed")

    data = r.json()
    return data["data"][0]["id"]


def select_station():
    try:
        raw_station = get_nearest_station_raw()

        if has_recent_data(raw_station):
            print("✅ Using closest station:", raw_station)
            return raw_station, "closest"

        fallback = get_nearest_station_with_data()
        print("⚠️ Using fallback station:", fallback)
        return fallback, "fallback_data"

    except Exception:
        print("❌ API error → using default station")
        return DEFAULT_STATION, "hard_fallback"


# ======================
# OBSERVATIONS (FROST)
# ======================

def get_observations(station_id):
    print("🔄 Fetching observations...")

    url = "https://frost.met.no/observations/v0.jsonld"

    end = datetime.now(UTC)
    start = end - timedelta(hours=12)

    params = {
        "sources": station_id,
        "elements": "air_temperature,wind_speed",  # ✅ include wind
        "referencetime": f"{start.isoformat()}/{end.isoformat()}"
    }

    r = requests.get(url, params=params, auth=(FROST_CLIENT_ID, ""))

    if r.status_code != 200:
        raise Exception(f"Frost error: {r.status_code}")

    return r.json()


def parse_observations(data, station_id, reason):
    rows = []

    for entry in data["data"]:
        values = {
            obs["elementId"]: obs["value"]
            for obs in entry["observations"]
        }

        rows.append({
            "time_utc": entry["referenceTime"],
            "temperature_obs": values.get("air_temperature"),
            "wind_obs": values.get("wind_speed"),  # ✅ may be None
            "station_id": station_id,
            "station_reason": reason,
            "timestamp_pipeline": datetime.now(UTC)
        })

    df = pd.DataFrame(rows)

    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    df = df.sort_values("time_utc")

    print("✅ Observation rows:", len(df))
    print("Latest obs:", df["time_utc"].max())

    return df


# ======================
# SAVE
# ======================

def save_data(df, filename):
    import pandas as pd
    import os

    # ✅ Clean incoming data
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["time_utc"])

    # ✅ Append if possible
    if os.path.exists(filename):
        old = pd.read_csv(filename)

        if sorted(old.columns) == sorted(df.columns):
            old["time_utc"] = pd.to_datetime(old["time_utc"], utc=True, errors="coerce")

            # ✅ align column order
            old = old[sorted(old.columns)]
            df = df[sorted(df.columns)]

            df = pd.concat([old, df], ignore_index=True)
        else:
            print("⚠️ Schema mismatch → overwriting file")

    # ✅ Final cleanup
    df = df.drop_duplicates(subset=["time_utc"])
    df = df.sort_values("time_utc")

    # ✅ Save
    df.to_csv(filename, index=False)

    print(f"✅ Saved {filename} with {len(df)} rows")

# ======================
# MAIN
# ======================

if __name__ == "__main__":

    print("🚀 Running weather pipeline")

    # Forecast
    forecast_df = get_forecast()
    save_data(forecast_df, FORECAST_FILE)

    # Observations
    station_id, reason = select_station()

    frost_raw = get_observations(station_id)
    obs_df = parse_observations(frost_raw, station_id, reason)

    save_data(obs_df, OBS_FILE)

    print("✅ Pipeline complete")