"""
TAHMO Shortwave Radiation Prediction Challenge
Highly optimized solution using per-station tree ensembles with advanced feature engineering
"""

import pandas as pd
import numpy as np
import os
import warnings
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.base import clone

warnings.filterwarnings('ignore')

print("=" * 80)
print("TAHMO RADIATION PREDICTION CHALLENGE - OPTIMIZED PER-STATION ENSEMBLE")
print("=" * 80)

# ============================================================================
# PART 1: FILE RESOLVING & DATA LOADING
# ============================================================================

def find_file(filename):
    """Robustly resolve file paths on both Windows local host and Linux mounts"""
    if os.path.exists(filename):
        return filename
    
    paths_to_try = [
        os.path.join('/mnt/user-data/uploads', filename),
        os.path.join('..', filename),
        os.path.join('data', filename),
    ]
    for p in paths_to_try:
        if os.path.exists(p):
            return p
    return filename

def save_file(df, filename):
    """Save submission file robustly to both current workspace and expected grading mount paths"""
    try:
        df.to_csv(filename, index=False)
        print(f"   ✓ Saved locally to {filename}")
    except Exception as e:
        print(f"   ! Could not save locally to {filename}: {e}")
        
    try:
        os.makedirs('/mnt/user-data/outputs', exist_ok=True)
        df.to_csv(os.path.join('/mnt/user-data/outputs', filename), index=False)
        print(f"   ✓ Saved to /mnt/user-data/outputs/{filename}")
    except Exception as e:
        pass

train_path = find_file('Train.csv')
test_path = find_file('Test.csv')
sub_path = find_file('SampleSubmission.csv')

print(f"\n[1] Loading datasets...")
print(f"   Train path resolved: {train_path}")
print(f"   Test path resolved: {test_path}")
print(f"   Submission path resolved: {sub_path}")

train_df = pd.read_csv(train_path)
test_df = pd.read_csv(test_path)
sample_submission = pd.read_csv(sub_path)

print(f"   Train shape: {train_df.shape}")
print(f"   Test shape: {test_df.shape}")
print(f"   Sample submission shape: {sample_submission.shape}")

# Save the original IDs and order of the test dataframe to align predictions later
test_ids = test_df['ID'].copy()

# ============================================================================
# PART 2: ADVANCED FEATURE ENGINEERING (SOLAR ANGLES, LAGS & ROLLING STATS)
# ============================================================================

print("\n[2] Executing advanced feature engineering...")

# Combine train and test to compute continuous lags and rolling windows without boundary edge-effects!
# We keep target variable 'radiation (W/m2)' separate.
y_train_full = train_df['radiation (W/m2)'].copy()
train_features = train_df.drop(columns=['radiation (W/m2)'])

train_features['is_train'] = True
test_df['is_train'] = False

combined_df = pd.concat([train_features, test_df], axis=0, ignore_index=True)
combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'])

# Sort by station and timestamp to calculate continuous temporal and weather sequences
combined_df = combined_df.sort_values(by=['station', 'timestamp']).reset_index(drop=True)

# 2.1 Basic Temporal features
combined_df['year'] = combined_df['timestamp'].dt.year
combined_df['month'] = combined_df['timestamp'].dt.month
combined_df['day'] = combined_df['timestamp'].dt.day
combined_df['hour'] = combined_df['timestamp'].dt.hour
combined_df['minute'] = combined_df['timestamp'].dt.minute
combined_df['day_of_week'] = combined_df['timestamp'].dt.dayofweek
combined_df['day_of_year'] = combined_df['timestamp'].dt.dayofyear

# Cyclical temporal encodings
combined_df['hour_sin'] = np.sin(2 * np.pi * (combined_df['hour'] + combined_df['minute'] / 60) / 24)
combined_df['hour_cos'] = np.cos(2 * np.pi * (combined_df['hour'] + combined_df['minute'] / 60) / 24)
combined_df['month_sin'] = np.sin(2 * np.pi * combined_df['month'] / 12)
combined_df['month_cos'] = np.cos(2 * np.pi * combined_df['month'] / 12)
combined_df['doy_sin'] = np.sin(2 * np.pi * combined_df['day_of_year'] / 365.25)
combined_df['doy_cos'] = np.cos(2 * np.pi * combined_df['day_of_year'] / 365.25)
combined_df['time_of_day'] = combined_df['hour'] * 60 + combined_df['minute']
combined_df['hours_from_noon'] = np.abs((combined_df['hour'] + combined_df['minute']/60) - 12)

# 2.2 Solar Geometry & Angles (Critical Physical Attributes)
day = combined_df['day_of_year']
hour = combined_df['hour'] + combined_df['minute'] / 60
lat = combined_df['latitude']
lon = combined_df['longitude']

# Declination
declination = 23.45 * np.sin(np.deg2rad(360 * (day - 81) / 365))

# Hour angle
hour_angle = 15 * (hour - 12)

# Elevation angle
sin_elev = (np.sin(np.deg2rad(lat)) * np.sin(np.deg2rad(declination)) +
            np.cos(np.deg2rad(lat)) * np.cos(np.deg2rad(declination)) *
            np.cos(np.deg2rad(hour_angle)))

elevation = np.rad2deg(np.arcsin(np.clip(sin_elev, -1, 1)))

combined_df['solar_elevation'] = elevation
combined_df['solar_zenith'] = 90 - elevation
combined_df['cos_zenith'] = np.cos(np.deg2rad(combined_df['solar_zenith']))

# Air mass (atm thickness proxy)
air_mass = np.where(elevation > 0, 1 / np.cos(np.deg2rad(90 - elevation)), 10.0)
combined_df['air_mass'] = np.clip(air_mass, 1, 10)
combined_df['air_mass'] = combined_df['air_mass'].fillna(10.0)

# Daytime indicator
combined_df['is_daytime'] = (combined_df['solar_elevation'] > 0).astype(float)

# 2.3 Station-Level Weather Deviations
combined_df['temp_deviation'] = combined_df['temperature (degrees Celsius)'] - combined_df.groupby('station')['temperature (degrees Celsius)'].transform('mean')
combined_df['humidity_deviation'] = combined_df['relativehumidity (-)'] - combined_df.groupby('station')['relativehumidity (-)'].transform('mean')

# 2.4 Weather Interaction Proxy features
combined_df['temp_humidity_interaction'] = combined_df['temperature (degrees Celsius)'] * combined_df['relativehumidity (-)']
combined_df['clear_sky_proxy'] = (1.0 - combined_df['relativehumidity (-)']) * combined_df['temperature (degrees Celsius)']

# 2.5 Continuous Lagged Weather Features (1h, 3h, 6h) within each station
print("   Calculating lag features...")
for lag in [4, 12, 24]:
    combined_df[f'temp_lag_{lag}'] = combined_df.groupby('station')['temperature (degrees Celsius)'].shift(lag)
    combined_df[f'humidity_lag_{lag}'] = combined_df.groupby('station')['relativehumidity (-)'].shift(lag)

# 2.6 Continuous Rolling Statistics (3h & 6h Windows) within each station
print("   Calculating rolling features...")
for window in [12, 24]:
    combined_df[f'temp_roll_mean_{window}'] = combined_df.groupby('station')['temperature (degrees Celsius)'].transform(lambda x: x.rolling(window, min_periods=1).mean())
    combined_df[f'humidity_roll_mean_{window}'] = combined_df.groupby('station')['relativehumidity (-)'].transform(lambda x: x.rolling(window, min_periods=1).mean())

# Define the complete feature column set
feature_cols = [
    'month_sin', 'month_cos', 'hour_sin', 'hour_cos', 'doy_sin', 'doy_cos',
    'day_of_week', 'time_of_day', 'hours_from_noon',
    'precipitation (mm)', 'relativehumidity (-)', 'temperature (degrees Celsius)',
    'latitude', 'longitude', 'elevation', 'installation_height',
    'solar_elevation', 'solar_zenith', 'cos_zenith', 'air_mass', 'is_daytime',
    'temp_deviation', 'humidity_deviation',
    'temp_humidity_interaction', 'clear_sky_proxy',
    'temp_lag_4', 'temp_lag_12', 'temp_lag_24',
    'humidity_lag_4', 'humidity_lag_12', 'humidity_lag_24',
    'temp_roll_mean_12', 'temp_roll_mean_24',
    'humidity_roll_mean_12', 'humidity_roll_mean_24'
]

# Impute initial sequence NaNs using the station's specific mean
print("   Imputing missing feature entries...")
for col in feature_cols:
    if combined_df[col].isna().sum() > 0:
        combined_df[col] = combined_df.groupby('station')[col].transform(lambda x: x.fillna(x.mean()))
        # Global fallback if a station has zero non-NaN values
        if combined_df[col].isna().sum() > 0:
            combined_df[col] = combined_df[col].fillna(combined_df[col].mean())

# Split back to train and test
train_fe = combined_df[combined_df['is_train'] == True].copy()
test_fe = combined_df[combined_df['is_train'] == False].copy()

# Add target back to train
train_fe['radiation (W/m2)'] = y_train_full.values

print(f"   ✓ Train feature matrix shape: {train_fe[feature_cols].shape}")
print(f"   ✓ Test feature matrix shape: {test_fe[feature_cols].shape}")

# ============================================================================
# PART 3: MODEL CONFIGURATIONS & FALLBACK
# ============================================================================

print("\n[3] Setting up high-performance ensembled regressors...")

rf_base = RandomForestRegressor(
    n_estimators=100,
    max_depth=15,
    min_samples_split=10,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1
)

et_base = ExtraTreesRegressor(
    n_estimators=100,
    max_depth=15,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)

hgb_base = HistGradientBoostingRegressor(
    max_iter=100,
    max_depth=8,
    learning_rate=0.05,
    random_state=42
)

# Train a fast global fallback model for any unrepresented stations (if any)
print("   Training global fallback ensembled models...")
X_train_global = train_fe[feature_cols].values
y_train_global = train_fe['radiation (W/m2)'].values

hgb_global = clone(hgb_base).fit(X_train_global, y_train_global)
print("   ✓ Global fallback completed")

# ============================================================================
# PART 4: PER-STATION TRAINING PIPELINE
# ============================================================================

print("\n[4] Running per-station ensembled training...")

station_predictions = []
stations = test_fe['station'].dropna().unique()

for idx, station_id in enumerate(stations):
    print(f"   [{idx+1:02d}/40] Training station {station_id}...")
    
    train_station = train_fe[train_fe['station'] == station_id].copy()
    test_station = test_fe[test_fe['station'] == station_id].copy()
    
    if len(test_station) == 0:
        continue
        
    X_test_st = test_station[feature_cols].values
    
    # Fallback to global model if training samples are critically insufficient
    if len(train_station) < 50:
        print(f"      ! Warning: Low samples for {station_id}. Using global fallback.")
        st_preds = hgb_global.predict(X_test_st)
    else:
        X_train_st = train_station[feature_cols].values
        y_train_st = train_station['radiation (W/m2)'].values
        
        # Fit ensembled models
        rf_model = clone(rf_base).fit(X_train_st, y_train_st)
        et_model = clone(et_base).fit(X_train_st, y_train_st)
        hgb_model = clone(hgb_base).fit(X_train_st, y_train_st)
        
        # Predict & blend
        rf_preds = rf_model.predict(X_test_st)
        et_preds = et_model.predict(X_test_st)
        hgb_preds = hgb_model.predict(X_test_st)
        
        st_preds = (rf_preds + et_preds + hgb_preds) / 3.0
        
    # Apply physical nighttime constraints: radiation is exactly 0 when sun is below horizon
    solar_elev = test_station['solar_elevation'].values
    st_preds = np.where(solar_elev <= 0, 0.0, st_preds)
    
    # Clip physically impossible predictions
    st_preds = np.clip(st_preds, 0.0, 1400.0)
    
    station_pred_df = pd.DataFrame({
        'ID': test_station['ID'].values,
        'prediction': st_preds
    })
    station_predictions.append(station_pred_df)

# Concatenate all station-specific predictions
pred_df = pd.concat(station_predictions, axis=0, ignore_index=True)

# ============================================================================
# PART 5: ALIGNMENT & SUBMISSION FILE WRITING
# ============================================================================

print("\n[5] Building final submission file...")

# Merge predictions with original SampleSubmission.csv to strictly preserve ID ordering
submission = sample_submission.copy()
submission = submission.merge(pred_df[['ID', 'prediction']], on='ID', how='left')

# In case of any merge NaNs (fill with 0)
submission['prediction'] = submission['prediction'].fillna(0.0)

submission['TargetMBE'] = submission['prediction']
submission['TargetRMSE'] = submission['prediction']

submission = submission.drop(columns=['prediction'])

# Save robustly to both local workspace and expected mounts
save_file(submission, 'submission.csv')

print("\n" + "=" * 80)
print("UPGRADED SOLUTION COMPLETED SUCCESSFULLY")
print("=" * 80)
print(f"   Submission shape: {submission.shape}")
print(f"   Mean prediction value: {submission['TargetMBE'].mean():.2f} W/m2")
print(f"   Max prediction value: {submission['TargetMBE'].max():.2f} W/m2")
print(f"   Zero value predictions (nighttime): {(submission['TargetMBE'] == 0.0).sum()} of {len(submission)}")
print("=" * 80)
