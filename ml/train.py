import argparse
import json
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from ml.preprocessing import DEFAULT_DATASET_PATH, FEATURE_COLUMNS, load_dataset


DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "rainfall_model.joblib"
DEFAULT_METRICS_PATH = Path(__file__).resolve().parent / "models" / "evaluation.json"


def build_models():
    imputer = SimpleImputer(strategy="median")
    return {
        "random_forest": Pipeline([
            ("imputer", imputer),
            ("model", RandomForestClassifier(n_estimators=120, random_state=42, n_jobs=-1, class_weight="balanced")),
        ]),
        "logistic_regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
        ]),
        "decision_tree": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", DecisionTreeClassifier(max_depth=12, random_state=42, class_weight="balanced")),
        ]),
    }


def evaluate_model(model, x_train, x_test, y_train, y_test):
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    return {
        "accuracy": accuracy_score(y_test, predicted),
        "precision": precision_score(y_test, predicted, zero_division=0),
        "recall": recall_score(y_test, predicted, zero_division=0),
        "f1": f1_score(y_test, predicted, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, predicted).tolist(),
    }


def train(dataset_path=DEFAULT_DATASET_PATH, model_path=DEFAULT_MODEL_PATH, metrics_path=DEFAULT_METRICS_PATH):
    features, target = load_dataset(dataset_path)
    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=42, stratify=target
    )
    cross_validator = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    evaluations = {}
    trained_models = build_models()
    for name, model in trained_models.items():
        evaluations[name] = evaluate_model(model, x_train, x_test, y_train, y_test)
        evaluations[name]["cv_f1"] = cross_val_score(model, features, target, cv=cross_validator, scoring="f1", n_jobs=1).mean()

    best_name = max(evaluations, key=lambda name: evaluations[name]["f1"])
    best_model = trained_models[best_name]
    model_path = Path(model_path)
    metrics_path = Path(metrics_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": best_model, "model_name": best_name, "feature_columns": FEATURE_COLUMNS}, model_path)
    metrics_path.write_text(json.dumps({
        "dataset": str(Path(dataset_path)),
        "rows": len(features),
        "features": FEATURE_COLUMNS,
        "target": "RainTomorrow (Yes=Rain, No=No Rain)",
        "best_model": best_name,
        "models": evaluations,
    }, indent=2), encoding="utf-8")
    return evaluations, best_name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train rainfall classifiers from historical weather data.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--metrics", default=str(DEFAULT_METRICS_PATH))
    args = parser.parse_args()
    results, best = train(args.dataset, args.model, args.metrics)
    print(json.dumps({"best_model": best, "models": results}, indent=2))
