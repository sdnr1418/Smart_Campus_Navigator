"""
Script 9 - Tune Best Model (Random Forest)
===========================================
Performs hyperparameter tuning for the Random Forest model selected in script 8.

Workflow:
  1. Train/Validation/Test split (60/20/20)
  2. RandomizedSearchCV on the train split (5-fold CV, macro-F1)
  3. Threshold selection on validation split (optimize macro-F1)
  4. Final evaluation on untouched test split

Artifacts:
  - Models/room_usability_model_tuned_rf.pkl
  - Results/training_report_tuned_rf.txt
  - Results/confusion_matrix_tuned_rf.png
"""

import os
import pickle
import warnings
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    f1_score,
    ConfusionMatrixDisplay,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATASET_CSV = os.path.join(PROJECT_ROOT, "Data", "room_usability_dataset.csv")
MODELS_DIR = os.path.join(PROJECT_ROOT, "Models")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "Results")

MODEL_PKL = os.path.join(MODELS_DIR, "room_usability_model_tuned_rf.pkl")
REPORT_TXT = os.path.join(RESULTS_DIR, "training_report_tuned_rf.txt")
CM_IMAGE = os.path.join(RESULTS_DIR, "confusion_matrix_tuned_rf.png")

FEATURE_COLS = [
    "day_of_week", "hour", "hour_sin", "hour_cos",
    "floor", "is_lab", "is_special",
    "room_overall_occupancy_rate", "block_hour_occupancy_rate",
    "neighbor_hour_occupancy_rate", "is_weekday", "room_popularity_bucket",
    "block_A", "block_B", "block_C", "block_D",
    "block_E", "block_F", "block_L",
]
TARGET_COL = "usable"
RANDOM_STATE = 42


def section(title: str, width: int = 64) -> str:
    return f"\n{'=' * width}\n{title}\n{'=' * width}"


def metrics_block(y_true, y_pred, y_prob) -> str:
    report = classification_report(
        y_true,
        y_pred,
        target_names=["Not Usable", "Usable"],
        digits=3,
    )
    cm = confusion_matrix(y_true, y_pred)
    auc = roc_auc_score(y_true, y_prob)

    out = report
    out += f"\nConfusion Matrix:\n{cm}"
    out += f"\nROC-AUC: {auc:.4f}"
    return out


def find_best_threshold(y_true, y_prob):
    best_threshold = 0.5
    best_f1 = -1.0

    for t in np.linspace(0.1, 0.9, 81):
        y_pred = (y_prob >= t).astype(int)
        score = f1_score(y_true, y_pred, average="macro")
        if score > best_f1:
            best_f1 = score
            best_threshold = float(t)

    return best_threshold, best_f1


def run():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    lines = []

    print("[1] Loading dataset...")
    df = pd.read_csv(DATASET_CSV)
    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values
    print(f"    Shape: {X.shape} | Class balance: {(y==1).sum()} usable / {(y==0).sum()} not-usable")

    # 60/20/20 split: first hold out test (20%), then split remaining 80% into train/val (75/25)
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval,
        y_trainval,
        test_size=0.25,
        random_state=RANDOM_STATE,
        stratify=y_trainval,
    )

    print(f"    Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    lines.append("ROOM USABILITY CLASSIFIER - RANDOM FOREST TUNING REPORT")
    lines.append(f"Dataset rows : {len(df)}")
    lines.append(f"Features     : {len(FEATURE_COLS)}")
    lines.append(
        f"Split sizes  : Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)} (60/20/20 stratified)"
    )
    lines.append(f"Class balance: {(y==1).sum()} usable | {(y==0).sum()} not-usable")

    print("\n[2] Running RandomizedSearchCV for Random Forest...")
    base_rf = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)

    param_dist = {
        "n_estimators": [100, 200, 300, 500, 800],
        "max_depth": [None, 10, 15, 20, 30],
        "min_samples_split": [2, 5, 10, 20],
        "min_samples_leaf": [1, 2, 4, 8],
        "max_features": ["sqrt", "log2", 0.5, 0.7, 1.0],
        "class_weight": [None, "balanced", "balanced_subsample"],
        "bootstrap": [True, False],
    }

    search = RandomizedSearchCV(
        estimator=base_rf,
        param_distributions=param_dist,
        n_iter=40,
        scoring="f1_macro",
        cv=5,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbose=1,
        refit=True,
    )

    search.fit(X_train, y_train)

    best_cv_f1 = search.best_score_
    best_params = search.best_params_
    best_rf_train = search.best_estimator_

    lines.append(section("HYPERPARAMETER SEARCH"))
    lines.append("Search method: RandomizedSearchCV")
    lines.append("Scoring      : f1_macro")
    lines.append("CV folds     : 5")
    lines.append("Iterations   : 40")
    lines.append(f"Best CV F1   : {best_cv_f1:.4f}")
    lines.append("Best Params:")
    for k, v in best_params.items():
        lines.append(f"  - {k}: {v}")

    # Top 10 candidates for visibility
    cv_results = pd.DataFrame(search.cv_results_).sort_values("rank_test_score")
    top_cols = [
        "rank_test_score",
        "mean_test_score",
        "std_test_score",
        "param_n_estimators",
        "param_max_depth",
        "param_min_samples_split",
        "param_min_samples_leaf",
        "param_max_features",
        "param_class_weight",
        "param_bootstrap",
    ]
    lines.append("\nTop 10 CV candidates:")
    for _, row in cv_results[top_cols].head(10).iterrows():
        lines.append(
            "  rank={:>2} | mean_f1={:.4f} (+/- {:.4f}) | n_est={} depth={} split={} leaf={} max_feat={} class_wt={} boot={}".format(
                int(row["rank_test_score"]),
                float(row["mean_test_score"]),
                float(row["std_test_score"]),
                row["param_n_estimators"],
                row["param_max_depth"],
                row["param_min_samples_split"],
                row["param_min_samples_leaf"],
                row["param_max_features"],
                row["param_class_weight"],
                row["param_bootstrap"],
            )
        )

    print(f"    Best CV macro-F1 = {best_cv_f1:.4f}")

    print("\n[3] Selecting classification threshold on validation split...")
    y_prob_val = best_rf_train.predict_proba(X_val)[:, 1]
    best_threshold, val_f1_best = find_best_threshold(y_val, y_prob_val)
    y_pred_val_default = (y_prob_val >= 0.5).astype(int)
    y_pred_val_tuned = (y_prob_val >= best_threshold).astype(int)

    val_f1_default = f1_score(y_val, y_pred_val_default, average="macro")

    lines.append(section("THRESHOLD TUNING (VALIDATION SET)"))
    lines.append(f"Default threshold (0.50) macro-F1 : {val_f1_default:.4f}")
    lines.append(f"Best threshold                    : {best_threshold:.2f}")
    lines.append(f"Best validation macro-F1          : {val_f1_best:.4f}")

    print(f"    Best threshold = {best_threshold:.2f} | Val macro-F1 = {val_f1_best:.4f}")

    print("\n[4] Refit best Random Forest on train+val, then evaluate on test...")
    best_rf_final = RandomForestClassifier(**best_params, random_state=RANDOM_STATE, n_jobs=-1)
    best_rf_final.fit(X_trainval, y_trainval)

    y_prob_test = best_rf_final.predict_proba(X_test)[:, 1]
    y_pred_test_default = (y_prob_test >= 0.5).astype(int)
    y_pred_test_tuned = (y_prob_test >= best_threshold).astype(int)

    f1_test_default = f1_score(y_test, y_pred_test_default, average="macro")
    f1_test_tuned = f1_score(y_test, y_pred_test_tuned, average="macro")

    lines.append(section("TEST SET EVALUATION (UNTOUCHED)"))
    lines.append(f"Macro-F1 @ threshold 0.50 : {f1_test_default:.4f}")
    lines.append(f"Macro-F1 @ tuned threshold: {f1_test_tuned:.4f}")
    lines.append("\nDetailed metrics with tuned threshold:")
    lines.append(metrics_block(y_test, y_pred_test_tuned, y_prob_test))

    # Feature importance from tuned model
    importances = pd.Series(best_rf_final.feature_importances_, index=FEATURE_COLS)
    importances = importances.sort_values(ascending=False)

    lines.append("\nFeature Importances (top 10):")
    for feat, imp in importances.head(10).items():
        bar = "#" * int(imp * 200)
        lines.append(f"  {feat:<25} {imp:.4f}  {bar}")

    print(f"    Test macro-F1 @0.50 = {f1_test_default:.4f}")
    print(f"    Test macro-F1 @tuned = {f1_test_tuned:.4f}")

    print(f"\n[5] Saving tuned model to {MODEL_PKL}")
    with open(MODEL_PKL, "wb") as f:
        pickle.dump(
            {
                "model": best_rf_final,
                "model_name": "Random Forest (Tuned)",
                "feature_cols": FEATURE_COLS,
                "threshold": best_threshold,
                "best_params": best_params,
                "cv_best_f1_macro": float(best_cv_f1),
            },
            f,
        )

    report_text = "\n".join(lines)
    with open(REPORT_TXT, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"    Tuning report saved to {REPORT_TXT}")

    print("[6] Generating confusion matrix plot...")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    fig.suptitle("Random Forest (Tuned) - Test Confusion Matrices", fontsize=13, fontweight="bold")

    cm_default = confusion_matrix(y_test, y_pred_test_default)
    disp_default = ConfusionMatrixDisplay(cm_default, display_labels=["Not Usable", "Usable"])
    disp_default.plot(ax=axes[0], colorbar=False, cmap="Blues")
    axes[0].set_title(f"Threshold 0.50\nF1={f1_test_default:.3f}", fontsize=10)

    cm_tuned = confusion_matrix(y_test, y_pred_test_tuned)
    disp_tuned = ConfusionMatrixDisplay(cm_tuned, display_labels=["Not Usable", "Usable"])
    disp_tuned.plot(ax=axes[1], colorbar=False, cmap="Blues")
    axes[1].set_title(f"Threshold {best_threshold:.2f}\nF1={f1_test_tuned:.3f}", fontsize=10)

    plt.tight_layout()
    plt.savefig(CM_IMAGE, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    Saved to {CM_IMAGE}")

    print("\n" + "=" * 64)
    print("RANDOM FOREST TUNING COMPLETE")
    print("=" * 64)
    print(f"Best CV macro-F1        : {best_cv_f1:.4f}")
    print(f"Validation best threshold: {best_threshold:.2f}")
    print(f"Test macro-F1 @0.50     : {f1_test_default:.4f}")
    print(f"Test macro-F1 @tuned    : {f1_test_tuned:.4f}")
    print(f"\nModel saved : {MODEL_PKL}")
    print(f"Report saved: {REPORT_TXT}")


if __name__ == "__main__":
    run()
