from pathlib import Path

import pandas as pd
import pytest

from ml.predict import MLPredictionError, prepare_features
from ml.preprocessing import DatasetError, load_dataset


DATASET = Path(__file__).parents[1] / "ml" / "data" / "weatherAUS.csv"


def test_real_dataset_is_preprocessed_without_live_api():
    features, target = load_dataset(DATASET)
    assert len(features) == len(target)
    assert list(features.columns) == ["temperature", "humidity", "pressure", "wind_speed", "precipitation", "cloud_cover"]
    assert set(target.unique()) == {0, 1}
    assert len(features) < 145460


def test_missing_dataset_is_reported(tmp_path):
    with pytest.raises(DatasetError, match="not found"):
        load_dataset(tmp_path / "missing.csv")


def test_weather_features_accept_optional_cloud_cover():
    features = prepare_features({
        "temperature": 29,
        "humidity": 82,
        "pressure": 1007,
        "wind_speed": 10,
        "precipitation": 0.1,
    })
    assert features.loc[0, "temperature"] == 29
    assert pd.isna(features.loc[0, "cloud_cover"])


def test_invalid_weather_value_is_rejected():
    with pytest.raises(MLPredictionError, match="temperature"):
        prepare_features({"temperature": "unknown"})
