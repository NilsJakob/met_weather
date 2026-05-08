import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time
import os
import requests
from datetime import datetime


if st.button("🔄 Force refresh"):
    st.cache_data.clear()





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


import streamlit as st
import pandas as pd
import requests
from io import StringIO

# -------------------------
# URLs
# -------------------------
FORECAST_FILE = "https://raw.githubusercontent.com/NilsJakob/met_weather/main/forecast.csv"
OBS_FILE = "https://raw.githubusercontent.com/NilsJakob/met_weather/main/observations.csv"

# -------------------------
# Helper functions
# -------------------------
def read_csv_url(url):
    response = requests.get(url)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))

def fix_time_column(df):
    df.columns = df.columns.str.strip().str.lower()
    if "time_utc" in df.columns:
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
        return df
    if "target_time_utc" in df.columns:
        df["time_utc"] = pd.to_datetime(df["target_time_utc"], utc=True)
        return df
    raise ValueError("No valid time column")

# -------------------------
# Load data
# -------------------------
@st.cache_data(ttl=60)
def load_data():
    f = read_csv_url(FORECAST_FILE)
    o = read_csv_url(OBS_FILE)
    return f, o

# -------------------------
# Merge
# -------------------------
def merge_data(f, o):
    f = fix_time_column(f)
    o = fix_time_column(o)

    df = pd.merge(
        f, o,
        on="time_utc",
        how="inner",
        suffixes=("_fc", "_obs")
    )
    return df

# -------------------------
# MAIN
# -------------------------
f, o = load_data()

df = merge_data(f, o)

st.dataframe(df)

if f is None or o is None:
    st.error("Failed to load data")
    st.stop()


# ✅ Everything below can safely use f and o
st.title("Weather Dashboard")

st.write("Forecast data:")
st.dataframe(f)

st.write("Observation data:")
st.dataframe(o)


#st.write("Forecast columns:", f.columns.tolist())
#st.write("Obs columns:", o.columns.tolist())

  
def merge_data(f, o):
    f = f.copy()
    o = o.copy()

    st.write("Columns BEFORE fix (forecast):", f.columns.tolist())
    st.write("Obs columns:", o.columns.tolist())

    f = fix_time_column(f)
    o = fix_time_column(o)

    df = pd.merge(
        f,
        o,
        on="time_utc",
        how="inner",
        suffixes=("_fc", "_obs")
    )

    return df


f, o = load_data()

if f is None or o is None:
    st.error("Failed to load data")
    st.stop()

df = merge_data(f, o)

st.dataframe(df)


df = merge_data(f, o)
nowcast_df = load_nowcast()

if df is None or len(df) < 1:
    st.warning("Not enough data yet. Come back later.")
    st.stop()

# ✅ data update time
if not df.empty:
    last_update = pd.to_datetime(df["time_utc"]).max()
    last_update_local = last_update.tz_convert("Europe/Oslo")

    st.caption(f"🕒 Last data update: {last_update_local.strftime('%Y-%m-%d %H:%M')}")


st.write(df.head())
st.write("Rows:", len(df))


from datetime import datetime
import pandas as pd

# ✅ last update
last_update = pd.to_datetime(df["time_utc"]).max()
last_update_local = last_update.tz_convert("Europe/Oslo")

st.caption(f"🕒 Last data update: {last_update_local.strftime('%Y-%m-%d %H:%M')}")

# ✅ thresholds
fresh_threshold = pd.Timedelta("2H")
warning_threshold = pd.Timedelta("4H")

# ✅ delay calculation
now_local = datetime.now(last_update_local.tzinfo)
delay = now_local - last_update_local

minutes = int(delay.total_seconds() / 60)
hours = minutes // 60
delay_str = f"{hours}h {minutes % 60}m"

# ✅ indicator
if delay <= fresh_threshold:
    st.success(f"🟢 Data is up-to-date (delay: {delay_str})")

elif delay <= warning_threshold:
    st.warning(f"🟡 Data is slightly delayed (delay: {delay_str})")

else:
    st.error(f"🔴 Data is outdated (delay: {delay_str})")



# ✅ METRICS
col1, col2, col3 = st.columns(3)

latest = df.iloc[-1]

col1.metric("Temp Forecast", f"{latest['temperature_fc']:.1f} °C")
col2.metric("Temp Observed", f"{latest['temperature_obs']:.1f} °C")
col3.metric("Error", f"{latest['temperature_fc'] - latest['temperature_obs']:.2f} °C")

df["error"] = df["temperature_fc"] - df["temperature_obs"]

# ✅ Metrics
mae = df["error"].abs().mean()
rmse = (df["error"]**2).mean()**0.5
bias = df["error"].mean()
st.subheader("📊 Forecast Performance")

col1, col2, col3 = st.columns(3)

col1.metric("MAE (°C)", f"{mae:.2f}")
col2.metric("RMSE (°C)", f"{rmse:.2f}")
col3.metric("Bias (°C)", f"{bias:.2f}")

st.subheader("📊 Performance by Lead Time")

grouped = df.groupby("lead_hours")["error"]

mae_by_lead = grouped.apply(lambda x: x.abs().mean())
rmse_by_lead = grouped.apply(lambda x: (x**2).mean()**0.5)

for lead in mae_by_lead.index:
    st.write(f"Lead {lead}h → MAE: {mae_by_lead[lead]:.2f}, RMSE: {rmse_by_lead[lead]:.2f}")


st.subheader("📈 Error Distribution")

import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.hist(df["error"], bins=20)

ax.set_xlabel("Error (°C)")
ax.set_ylabel("Frequency")

st.pyplot(fig)






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


latest_time = df["time_utc"].max()
now = pd.Timestamp.utcnow()

st.write("Now (UTC):", now)
st.write("Latest data time:", latest_time)
st.write("Delay:", now - latest_time)