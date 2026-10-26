from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.preprocessing import DEFAULT_DATASET_PATH, FEATURE_COLUMNS
from ml.train import DEFAULT_MODEL_PATH


class MLPredictionError(RuntimeError):
    """Raised when the persisted rainfall model cannot produce a prediction."""


@lru_cache(maxsize=1)
def load_model(model_path=DEFAULT_MODEL_PATH):
    path = Path(model_path)
    if not path.exists():
        raise MLPredictionError(
            f"AI rainfall model is not available. Train it with: python -m ml.train --dataset {DEFAULT_DATASET_PATH}"
        )
    try:
        artifact = joblib.load(path)
        model = artifact["model"]
        feature_columns = artifact["feature_columns"]
    except (OSError, KeyError, ValueError, ImportError) as error:
        raise MLPredictionError("The AI rainfall model could not be loaded.") from error
    if list(feature_columns) != FEATURE_COLUMNS or not hasattr(model, "predict_proba"):
        raise MLPredictionError("The AI rainfall model has an incompatible format.")
    return artifact


def prepare_features(current_weather):
    if not isinstance(current_weather, dict):
        raise MLPredictionError("Current weather data is not valid for AI prediction.")
    values = {
        "temperature": current_weather.get("temperature"),
        "humidity": current_weather.get("humidity"),
        "pressure": current_weather.get("pressure"),
        "wind_speed": current_weather.get("wind_speed"),
        "precipitation": current_weather.get("precipitation"),
        "cloud_cover": current_weather.get("cloud_cover"),
    }
    for name, value in values.items():
        if value is not None:
            try:
                values[name] = float(value)
            except (TypeError, ValueError) as error:
                raise MLPredictionError(f"The weather value for {name} is invalid.") from error
            if not np.isfinite(values[name]):
                raise MLPredictionError(f"The weather value for {name} is invalid.")
    return pd.DataFrame([values], columns=FEATURE_COLUMNS)


def _risk_level(probability):
    if probability >= 0.75:
        return "High"
    if probability >= 0.5:
        return "Moderate"
    return "Low"


def predict_rain(current_weather, model_path=DEFAULT_MODEL_PATH):
    try:
        artifact = load_model(model_path)
        features = prepare_features(current_weather)
        model = artifact["model"]
        probability = float(model.predict_proba(features)[0][1])
        predicted = int(model.predict(features)[0])
    except MLPredictionError:
        raise
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise MLPredictionError("The AI rainfall prediction could not be calculated.") from error

    importances = getattr(model.named_steps.get("model"), "feature_importances_", None)
    factors = []
    if importances is not None:
        factors = [
            {"name": name.replace("_", " ").title(), "importance": round(float(score), 3)}
            for name, score in sorted(zip(FEATURE_COLUMNS, importances), key=lambda item: item[1], reverse=True)[:4]
        ]
    return {
        "probability": probability,
        "probability_percent": round(probability * 100),
        "prediction": "Rain Expected" if predicted else "No Rain Expected",
        "risk_level": _risk_level(probability),
        "factors": factors,
        "model_name": artifact.get("model_name", "Random Forest"),
    }
