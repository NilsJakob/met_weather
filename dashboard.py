import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time
import os

import requests

LAT = 59.137344
LON = 9.671435
HEADERS = {
    "User-Agent": "usn_smart_grid_lab_porsgrunn/v0.2 nils.j.johannesen@usn.no"
}

@st.cache_data(ttl=300)
def load_nowcast():
    url = f"https://api.met.no/weatherapi/nowcast/2.0/complete?lat={LAT}&lon={LON}"

    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        return None

    data = r.json()

    ts = data["properties"]["timeseries"]

    rows = []

    for t in ts[:24]:
        time = t["time"]
       
        instant = t["data"].get("instant", {}).get("details", {})
        
        precip = t["data"].get("next_1_hours", {}) \
                          .get("details", {}) \
                          .get("precipitation_amount", 0)

        rows.append({
            "time": pd.to_datetime(time, utc=True),
            "temperature": instant.get("air_temperature", None),
            "precipitation": precip
        })


    return pd.DataFrame(rows)


FORECAST_FILE = "forecast.csv"
OBS_FILE = "observations.csv"

st.set_page_config(page_title="Weather Dashboard", layout="wide")

st.title("🌦️ Weather Forecast Dashboard (USN smart grid LAB)")

# Auto-refresh
st.caption("Auto-updates every 60 seconds")
time.sleep(1)


@st.cache_data(ttl=60)


def load_data():
    f = pd.read_csv(FORECAST_FILE)
    o = pd.read_csv(OBS_FILE)

    # ✅ FIX: convert to datetime
    f["target_time_utc"] = pd.to_datetime(f["target_time_utc"], utc=True)
    o["time_utc"] = pd.to_datetime(o["time_utc"], utc=True)

    return f, o


  
def merge_data():
    f, o = load_data()

    f = f.sort_values("target_time_utc")
    o = o.sort_values("time_utc")

    df = pd.merge_asof(
        f,
        o,
        left_on="target_time_utc",
        right_on="time_utc",
        direction="nearest",
        tolerance=pd.Timedelta("2H"),
        suffixes=("_fc", "_obs")
    )

    print("Columns after merge:", df.columns)

    # ✅ Safe cleaning
    if "temperature_obs" in df.columns:
        df = df.dropna(subset=["temperature_obs"])
    else:
        print("⚠️ No observation matches yet")

    return df



df = merge_data()
nowcast_df = load_nowcast()

if df is None or len(df) < 1:
    st.warning("Not enough data yet. Come back later.")
    st.stop()


# ✅ METRICS
col1, col2, col3 = st.columns(3)

latest = df.iloc[-1]

col1.metric("Temp Forecast", f"{latest['temperature_fc']:.1f} °C")
col2.metric("Temp Observed", f"{latest['temperature_obs']:.1f} °C")
col3.metric("Error", f"{latest['temperature_fc'] - latest['temperature_obs']:.2f} °C")


# ✅ TEMPERATURE PLOT
st.subheader("🌡️ Temperature: Forecast vs Observed")

fig1, ax1 = plt.subplots()

ax1.plot(df["target_time_utc"], df["temperature_fc"], label="Forecast")
ax1.plot(df["target_time_utc"], df["temperature_obs"], label="Observed")

ax1.set_xlabel("Time")
ax1.set_ylabel("Temperature (°C)")
ax1.legend()
plt.xticks(rotation=30)

st.pyplot(fig1)


# ✅ ERROR PLOT
st.subheader("📉 Forecast Error")

df["error"] = df["temperature_fc"] - df["temperature_obs"]

fig2, ax2 = plt.subplots()

ax2.plot(df["target_time_utc"], df["error"])
ax2.axhline(0)

ax2.set_xlabel("Time")
ax2.set_ylabel("Error (°C)")

plt.xticks(rotation=30)

st.pyplot(fig2)


# ✅ IRRADIANCE
if "irradiance_fc" in df.columns:
    st.subheader("☀️ Irradiance Forecast")

    fig3, ax3 = plt.subplots()

    ax3.plot(df["target_time_utc"], df["irradiance_fc"], label="Forecast")

    if "irradiance_obs" in df.columns:
        ax3.plot(df["target_time_utc"], df["irradiance_obs"], label="Observed")

    ax3.set_ylabel("W/m²")
    ax3.legend()

    plt.xticks(rotation=30)

    st.pyplot(fig3)


# ✅ DATA TABLE
with st.expander("🔍 Show raw data"):
    st.dataframe(df.tail(20))


st.subheader("🌧️ Nowcast (Next ~2 Hours)")

if nowcast_df is None or len(nowcast_df) == 0:
    st.warning("No nowcast data available")
else:
    fig, ax = plt.subplots()

    ax.plot(nowcast_df["time"], nowcast_df["precipitation"])
    ax.set_ylabel("mm")
    ax.set_xlabel("Time")

    plt.xticks(rotation=30)

    st.pyplot(fig)
