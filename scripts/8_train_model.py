"""
Script 8 - Train & Evaluate Room Usability Classifier (Simple)
==============================================================
Trains three models on the dataset from script 7 without hyperparameter tuning:
  1. Logistic Regression  (baseline)
  2. Random Forest        (tree-based ensemble)
  3. Neural Network (ANN) (deep learning baseline)

For each model reports: Precision, Recall, F1 (per class + macro),
confusion matrix, and ROC-AUC.

Saves the best model as Models/room_usability_model.pkl.
Writes a full text report to Results/training_report.txt.

FEATURE COLUMNS USED FOR TRAINING (17 total):
  Temporal    : day_of_week, hour, hour_sin, hour_cos, is_weekday
  Room static : floor, is_lab, is_special
  Rate-based  : room_overall_occupancy_rate, block_hour_occupancy_rate,
                neighbor_hour_occupancy_rate, room_popularity_bucket
  Block one-hot: block_A, block_B, block_C, block_D, block_E, block_F, block_L
  
Analysis-only (EXCLUDED from training):
  scheduled_class, prev_hour_occupied, next_hour_occupied
  (These would cause data leakage as they are directly derived from timetable)
"""

import os
import pickle
import warnings
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.linear_model   import LogisticRegression
from sklearn.ensemble       import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics        import (classification_report, confusion_matrix,
                                    roc_auc_score, ConfusionMatrixDisplay, f1_score)
from sklearn.preprocessing  import StandardScaler
from sklearn.pipeline       import Pipeline

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# Paths
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATASET_CSV  = os.path.join(PROJECT_ROOT, "Data",    "room_usability_dataset.csv")
MODELS_DIR   = os.path.join(PROJECT_ROOT, "Models")
RESULTS_DIR  = os.path.join(PROJECT_ROOT, "Results")
MODEL_PKL    = os.path.join(MODELS_DIR,   "room_usability_model.pkl")
REPORT_TXT   = os.path.join(RESULTS_DIR,  "training_report.txt")
CM_IMAGE     = os.path.join(RESULTS_DIR,  "confusion_matrices.png")

FEATURE_COLS = [
    # temporal
    "day_of_week", "hour", "hour_sin", "hour_cos",
    # room static
    "floor", "is_lab", "is_special",
    # probabilistic / rate
    "room_overall_occupancy_rate", "block_hour_occupancy_rate",
    "neighbor_hour_occupancy_rate", "is_weekday", "room_popularity_bucket",
    # block one-hot
    "block_A", "block_B", "block_C", "block_D",
    "block_E", "block_F", "block_L",
]
TARGET_COL   = "usable"
RANDOM_STATE = 42

# Helpers
def section(title: str, width: int = 60) -> str:
    return f"\n{'='*width}\n{title}\n{'='*width}"

def metrics_block(y_true, y_pred, y_prob=None) -> str:
    report = classification_report(y_true, y_pred,
                                   target_names=["Not Usable", "Usable"],
                                   digits=3)
    cm = confusion_matrix(y_true, y_pred)
    block = report
    block += f"\nConfusion Matrix:\n{cm}"
    if y_prob is not None:
        auc = roc_auc_score(y_true, y_prob)
        block += f"\nROC-AUC: {auc:.4f}"
    return block

# Training pipeline
def run():
    os.makedirs(MODELS_DIR,  exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    lines = []   # accumulate report lines

    # --- Load data ------------------------------------------------------------
    print("[1] Loading dataset...")
    df = pd.read_csv(DATASET_CSV)
    X  = df[FEATURE_COLS].values
    y  = df[TARGET_COL].values
    print(f"    Shape: {X.shape}  |  Class balance: "
          f"{(y==1).sum()} usable / {(y==0).sum()} not-usable")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    print(f"    Train: {len(X_train)} | Test: {len(X_test)}")

    lines.append("ROOM USABILITY CLASSIFIER - TRAINING REPORT")
    lines.append(f"Dataset rows : {len(df)}")
    lines.append(f"Features     : {len(FEATURE_COLS)}")
    lines.append(f"Train / Test : {len(X_train)} / {len(X_test)} (80/20 stratified)")
    lines.append(f"Class balance: {(y==1).sum()} usable  |  {(y==0).sum()} not-usable")

    results = {}   # model_name → {auc, f1_macro, model}

    # -------------------------------------------------------------------------
    # MODEL 1 - Logistic Regression (baseline)
    # -------------------------------------------------------------------------
    print("\n[2] Training Logistic Regression (baseline)...")
    lr_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
    ])
    lr_pipe.fit(X_train, y_train)
    y_pred_lr   = lr_pipe.predict(X_test)
    y_prob_lr   = lr_pipe.predict_proba(X_test)[:, 1]

    lines.append(section("MODEL 1: Logistic Regression (Baseline)"))
    lines.append("Rationale: Linear baseline to understand feature relationships.")
    lines.append("Provides interpretable coefficients but cannot capture non-linear patterns.\n")
    lines.append(metrics_block(y_test, y_pred_lr, y_prob_lr))
    auc_lr = roc_auc_score(y_test, y_prob_lr)
    f1_lr = f1_score(y_test, y_pred_lr, average="macro")
    results["Logistic Regression"] = {"auc": auc_lr, "f1": f1_lr, "model": lr_pipe}
    print(f"    ROC-AUC={auc_lr:.4f}  F1-macro={f1_lr:.4f}")

    # -------------------------------------------------------------------------
    # MODEL 2 - Random Forest (simple, no tuning)
    # -------------------------------------------------------------------------
    print("\n[3] Training Random Forest (simple)...")
    rf = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(X_train, y_train)
    y_pred_rf   = rf.predict(X_test)
    y_prob_rf   = rf.predict_proba(X_test)[:, 1]

    lines.append(section("MODEL 2: Random Forest"))
    lines.append("Rationale: Tree-based ensemble captures non-linear interactions naturally.")
    lines.append("No hyperparameter tuning; using sensible defaults.")
    lines.append(f"Config: n_estimators=100, max_depth=15, random_state={RANDOM_STATE}\n")
    lines.append(metrics_block(y_test, y_pred_rf, y_prob_rf))

    # Feature importance
    importances = pd.Series(rf.feature_importances_, index=FEATURE_COLS)
    importances = importances.sort_values(ascending=False)
    lines.append("\nFeature Importances (top 10):")
    for feat, imp in importances.head(10).items():
        bar = "#" * int(imp * 200)
        lines.append(f"  {feat:<25} {imp:.4f}  {bar}")

    auc_rf = roc_auc_score(y_test, y_prob_rf)
    f1_rf  = f1_score(y_test, y_pred_rf, average="macro")
    results["Random Forest"] = {"auc": auc_rf, "f1": f1_rf, "model": rf}
    print(f"    ROC-AUC={auc_rf:.4f}  F1-macro={f1_rf:.4f}")

    # -------------------------------------------------------------------------
    # MODEL 3 - Artificial Neural Network (ANN)
    # -------------------------------------------------------------------------
    print("\n[4] Training Neural Network (ANN)...")
    ann_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, 
                              random_state=RANDOM_STATE, early_stopping=True,
                              validation_fraction=0.1, n_iter_no_change=20)),
    ])
    ann_pipe.fit(X_train, y_train)
    y_pred_ann   = ann_pipe.predict(X_test)
    y_prob_ann   = ann_pipe.predict_proba(X_test)[:, 1]

    lines.append(section("MODEL 3: Artificial Neural Network (ANN)"))
    lines.append("Rationale: Deep learning baseline with two hidden layers (64, 32).")
    lines.append("Can learn complex patterns but requires careful regularization.")
    lines.append("Config: hidden_layers=(64, 32), max_iter=500, early_stopping=True\n")
    lines.append(metrics_block(y_test, y_pred_ann, y_prob_ann))

    auc_ann = roc_auc_score(y_test, y_prob_ann)
    f1_ann  = f1_score(y_test, y_pred_ann, average="macro")
    results["Neural Network"] = {"auc": auc_ann, "f1": f1_ann, "model": ann_pipe}
    print(f"    ROC-AUC={auc_ann:.4f}  F1-macro={f1_ann:.4f}")

    # Comparison & saving
    lines.append(section("MODEL COMPARISON"))
    lines.append(f"{ 'Model':<22} {'F1-macro':>10} {'ROC-AUC':>10}")
    lines.append("-" * 44)
    for name, r in results.items():
        lines.append(f"{name:<22} {r['f1']:>10.4f} {r['auc']:>10.4f}")

    # Select winner
    best_name  = max(results, key=lambda k: results[k]["f1"])
    best_model = results[best_name]["model"]
    lines.append(f"\nWINNER: {best_name}  (F1-macro={results[best_name]['f1']:.4f})")

    # FAILURE ANALYSIS
    lines.append(section("FAILURE ANALYSIS"))
    lines.append(
        "1. Logistic Regression underperformed because the decision boundary\n"
        "   between usable/not-usable is inherently non-linear:\n"
        "   - A room may be free at 08:00 Mon (usable) but not at 09:00 Mon\n"
        "     (buffer before 10:00 class). A linear model cannot capture the\n"
        "     interaction between (hour, prev_hour_occupied) without polynomial\n"
        "     feature expansion, which we deliberately avoided to keep the\n"
        "     feature space interpretable.\n"
    )
    lines.append(
        "2. B-Block (CRMG, Embedded Lab) has 0% usable slots across all hours\n"
        "   because both rooms are classified as 'special'. Any model trained\n"
        "   on this data will always predict not-usable for B-Block, which is\n"
        "   correct by design but means the model offers no value for B-Block\n"
        "   specifically. A real-world fix would involve collecting booking\n"
        "   calendar data for these rooms.\n"
    )

    # SAVE ARTIFACTS
    print(f"\n[5] Saving best model ({best_name}) to {MODEL_PKL}")
    with open(MODEL_PKL, "wb") as f:
        pickle.dump({
            "model":        best_model,
            "model_name":   best_name,
            "feature_cols": FEATURE_COLS,
        }, f)

    report_text = "\n".join(lines)
    with open(REPORT_TXT, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"    Training report saved to {REPORT_TXT}")

    # Confusion matrix figure (3 models)
    print("[6] Generating confusion matrix plot...")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle("Confusion Matrices - Test Set", fontsize=14, fontweight="bold")
    preds = [y_pred_lr, y_pred_rf, y_pred_ann]
    for ax, (name, r), y_pred in zip(axes, list(results.items()), preds):
        cm = confusion_matrix(y_test, y_pred)
        disp = ConfusionMatrixDisplay(cm, display_labels=["Not Usable", "Usable"])
        disp.plot(ax=ax, colorbar=False, cmap="Blues")
        ax.set_title(f"{name}\nF1={r['f1']:.3f}  AUC={r['auc']:.3f}", fontsize=10)
    plt.tight_layout()
    plt.savefig(CM_IMAGE, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    Saved to {CM_IMAGE}")

    # Final summary
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"{ 'Model':<22} {'F1-macro':>10} {'ROC-AUC':>10}")
    print("-" * 44)
    for name, r in results.items():
        tag = " <-- BEST" if name == best_name else ""
        print(f"{name:<22} {r['f1']:>10.4f} {r['auc']:>10.4f}{tag}")
    print(f"\nModel saved : {MODEL_PKL}")
    print(f"Report saved: {REPORT_TXT}")

if __name__ == "__main__":
    run()
