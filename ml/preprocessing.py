from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = PROJECT_ROOT / "ml" / "data" / "weatherAUS.csv"
FEATURE_COLUMNS = ["temperature", "humidity", "pressure", "wind_speed", "precipitation", "cloud_cover"]
DATASET_COLUMNS = {
    "temperature": "Temp3pm",
    "humidity": "Humidity3pm",
    "pressure": "Pressure3pm",
    "wind_speed": "WindSpeed3pm",
    "precipitation": "Rainfall",
    "cloud_cover": "Cloud3pm",
}
TARGET_COLUMN = "RainTomorrow"


class DatasetError(ValueError):
    """Raised when the historical training dataset cannot be used."""


def load_dataset(dataset_path=DEFAULT_DATASET_PATH):
    path = Path(dataset_path)
    if not path.exists():
        raise DatasetError(f"Training dataset not found: {path}")

    try:
        source = pd.read_csv(path)
    except (OSError, ValueError) as error:
        raise DatasetError("The training dataset could not be read.") from error

    required_columns = set(DATASET_COLUMNS.values()) | {TARGET_COLUMN}
    missing_columns = required_columns.difference(source.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise DatasetError(f"The training dataset is missing columns: {missing}")

    frame = source[list(DATASET_COLUMNS.values()) + [TARGET_COLUMN]].copy()
    frame = frame.drop_duplicates()
    for column in DATASET_COLUMNS.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame[TARGET_COLUMN] = frame[TARGET_COLUMN].astype("string").str.strip().str.lower()
    frame = frame[frame[TARGET_COLUMN].isin(["yes", "no"])].dropna(subset=[TARGET_COLUMN])
    if frame.empty or frame[TARGET_COLUMN].nunique() < 2:
        raise DatasetError("The training dataset needs both Rain and No Rain examples.")

    features = frame[list(DATASET_COLUMNS.values())].rename(
        columns={source_name: feature_name for feature_name, source_name in DATASET_COLUMNS.items()}
    )
    target = frame[TARGET_COLUMN].map({"yes": 1, "no": 0}).astype("int8")
    return features, target
