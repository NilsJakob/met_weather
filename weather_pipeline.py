import requests
import pandas as pd
import os
import time
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo



BASE_PATH = r"C:\Users\njoha\OneDrive - USN\energy_data\met_weather"
os.chdir(BASE_PATH)

print("✅ Using working directory:", os.getcwd())



# ======================
# CONFIG
# ======================
#59.137344, 9.671435
LAT = 59.137344
LON = 9.671435

URL = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LAT}&lon={LON}"

HEADERS = {
    "User-Agent": "usn_smart_grid_lab_porsgrunn nils.j.johannesen@usn.no"
}


FORECAST_FILE = os.path.join(BASE_PATH, "forecast.csv")
OBS_FILE = os.path.join(BASE_PATH, "observations.csv")


# ======================
# TIME HANDLING
# ======================

def add_time_fields(utc_string):
    dt_utc = datetime.fromisoformat(utc_string.replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(ZoneInfo("Europe/Oslo"))

    return dt_utc.isoformat(), dt_local.isoformat()


# ======================
# PARSE DATA
# ======================

def parse(ts):
    d = ts["data"]["instant"]["details"]
    t_utc, t_local = add_time_fields(ts["time"])

    return {
        "time_utc": t_utc,
        "time_local": t_local,
        "temperature": d["air_temperature"],
        "wind": d["wind_speed"],
        "humidity": d["relative_humidity"],
        "irradiance": d.get("surface_downwelling_shortwave_flux_in_air", None)
    }


# ======================
# SAFE FILE WRITE
# ======================

def safe_write(df, filename):
    for _ in range(5):
        try:
            df.to_csv(
                filename,
                mode="a",
                header=not os.path.exists(filename),
                index=False
            )
            return
        except PermissionError:
            print(f"File {filename} is locked, retrying...")
            time.sleep(2)

    raise Exception(f"Could not write to {filename}")


# ======================
# GITHUB PUSH
# ======================

def git_push():
    try:
        subprocess.run(["git", "add", "."], check=True)

        # Only commit if changes exist
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])

        if result.returncode == 1:
            subprocess.run(
                ["git", "commit", "-m", f"Auto update {datetime.now()}"],
                check=True
            )
            subprocess.run(["git", "push"], check=True)
            print("✅ Changes pushed to GitHub")
        else:
            print("No changes to commit")

    except Exception as e:
        print("Git error:", e)


# ======================
# MAIN PIPELINE
# ======================

def run():
    try:
        response = requests.get(URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        timeseries = data["properties"]["timeseries"]

        # Run time
        now_utc = datetime.now(timezone.utc).replace(microsecond=0)
        now_local = now_utc.astimezone(ZoneInfo("Europe/Oslo"))

        # ======================
        # OBSERVATION
        # ======================
        obs = parse(timeseries[0])

        obs_df = pd.DataFrame([{
            "time_utc": obs["time_utc"],
            "time_local": obs["time_local"],
            "temperature": obs["temperature"],
            "wind": obs["wind"],
            "humidity": obs["humidity"],
            "irradiance": obs["irradiance"]
        }])

        safe_write(obs_df, OBS_FILE)

        # ======================
        # FORECAST
        # ======================
        fc1 = parse(timeseries[1])
        fc24 = parse(timeseries[24])

        forecast_df = pd.DataFrame([
            {
                "run_time_utc": now_utc.isoformat(),
                "run_time_local": now_local.isoformat(),

                "target_time_utc": fc1["time_utc"],
                "target_time_local": fc1["time_local"],

                "lead_hours": 1,
                "temperature": fc1["temperature"],
                "wind": fc1["wind"],
                "humidity": fc1["humidity"],
                "irradiance": fc1["irradiance"]
            },
            {
                "run_time_utc": now_utc.isoformat(),
                "run_time_local": now_local.isoformat(),

                "target_time_utc": fc24["time_utc"],
                "target_time_local": fc24["time_local"],

                "lead_hours": 24,
                "temperature": fc24["temperature"],
                "wind": fc24["wind"],
                "humidity": fc24["humidity"],
                "irradiance": fc24["irradiance"]
            }
        ])

        safe_write(forecast_df, FORECAST_FILE)

        print(f"✅ Updated at {now_utc.isoformat()}")

        # ======================
        # GIT PUSH
        # ======================
        git_push()

    except Exception as e:
        print("Error:", e)


# ======================
# ENTRY POINT
# ======================

if __name__ == "__main__":
    run()