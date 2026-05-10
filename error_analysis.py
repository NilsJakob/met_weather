import pandas as pd
import matplotlib.pyplot as plt

print("🔄 Loading data...")

# ========================
# ✅ LOAD DATA
# ========================
forecast_df = pd.read_csv("forecast.csv")
obs_df = pd.read_csv("observations.csv")


# FIX: use correct column
if "temperature_obs" not in obs_df.columns and "temperature" in obs_df.columns:
    obs_df["temperature_obs"] = obs_df["temperature"]


if "wind_obs" not in obs_df.columns and "wind" in obs_df.columns:
    obs_df["wind_obs"] = obs_df["wind"]


# ========================
# ✅ PARSE TIMESTAMPS
# ========================
forecast_df["time_utc"] = pd.to_datetime(
    forecast_df["time_utc"], utc=True, errors="coerce", format="mixed"
)

obs_df["time_utc"] = pd.to_datetime(
    obs_df["time_utc"], utc=True, errors="coerce", format="mixed"
)

# ========================
# ✅ CLEAN DATA
# ========================
forecast_df = forecast_df.dropna(subset=["time_utc"])
obs_df = obs_df.dropna(subset=["time_utc"])

forecast_df = forecast_df.drop_duplicates(subset=["time_utc"])
obs_df = obs_df.drop_duplicates(subset=["time_utc"])

print("Forecast range:")
print(forecast_df["time_utc"].min(), forecast_df["time_utc"].max())

print("\nObservation range:")
print(obs_df["time_utc"].min(), obs_df["time_utc"].max())

#obs_df["temperature_obs"] = obs_df["temperature"]

if "temperature_obs" not in obs_df.columns:
    raise ValueError("temperature_obs column missing — pipeline issue")

# ========================
# ✅ CREATE COMMON TIME GRID
# ========================
start = max(forecast_df["time_utc"].min(), obs_df["time_utc"].min())
end   = min(forecast_df["time_utc"].max(), obs_df["time_utc"].max())

time_grid = pd.DataFrame({
    "time_utc": pd.date_range(start=start, end=end, freq="1h", tz="UTC")
})

print("\nForecast sample:")
print(forecast_df.head())

print("\nObs sample:")
print(obs_df.head())
# ========================
# ✅ ALIGN BOTH DATASETS TO SAME GRID
# ========================
forecast_df = pd.merge(time_grid, forecast_df, on="time_utc", how="left")

obs_df = pd.merge(time_grid, obs_df, on="time_utc", how="left")

# Fill missing observations forward (important!)
obs_df["temperature_obs"] = obs_df["temperature_obs"].ffill()
if "wind_obs" in obs_df.columns:
    obs_df["wind_obs"] = obs_df["wind_obs"].ffill()

# ========================
# ✅ FINAL MERGE
# ========================
print("🔄 Merging forecast and observations...")

df = pd.merge(forecast_df, obs_df, on="time_utc", how="inner")

# ========================
# ✅ CLEAN + COMPUTE ERROR
# ========================
df = df.dropna(subset=["temperature_fc", "temperature_obs"])

df["temp_error"] = df["temperature_fc"] - df["temperature_obs"]

# ========================
# ✅ METRICS
# ========================
print("\n🔄 Calculating errors...")

mae = df["temp_error"].abs().mean()
bias = df["temp_error"].mean()

print("\n📊 BASIC METRICS")
print("Mean error (bias):", round(bias, 2))
print("Mean absolute error (MAE):", round(mae, 2))

# ========================
# ✅ STATION USAGE
# ========================
if "station_reason" in df.columns:
    print("\n📍 Station usage:")
    print(df["station_reason"].value_counts())
else:
    print("\n📍 Station usage: not available")

# ========================
# ✅ DEBUG OUTPUT
# ========================
print("\n🔍 Sample merged data:")
print(df[[
    "time_utc",
    "temperature_fc",
    "temperature_obs",
    "temp_error"
]].head())

# ========================
# ✅ SAVE RESULT
# ========================
df.to_csv("merged_weather.csv", index=False)

print("\n✅ Analysis complete. Saved → merged_weather.csv")

# ========================
# ✅ PLOTS
# ========================
print("📈 Showing plot...")

# ✅ SAFETY CHECK
if len(df) > 0:

    # Forecast vs observation plot
    df.plot(
        x="time_utc",
        y=["temperature_fc", "temperature_obs"],
        title="Forecast vs Observation",
        marker="o"
    )

    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    # Error plot
    df.plot(
        x="time_utc",
        y="temp_error",
        kind="bar",
        title="Forecast Error"
    )

    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

else:
    print("⚠️ No data to plot")