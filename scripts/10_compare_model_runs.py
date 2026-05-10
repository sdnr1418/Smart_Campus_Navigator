"""
Script 12 - Compare Model Runs
==============================
Compares the main room usability model runs and writes a single summary report.

Compared runs:
  1. Baseline Random Forest
  2. Tuned Random Forest
  3. Tuned Logistic Regression
  4. Tuned ANN

The script reads the already-generated training reports, extracts the key metrics,
then writes a ranked summary to Results/model_comparison_summary.txt.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RESULTS_DIR = os.path.join(PROJECT_ROOT, "Results")

BASELINE_REPORT = os.path.join(RESULTS_DIR, "training_report.txt")
TUNED_RF_REPORT = os.path.join(RESULTS_DIR, "training_report_tuned_rf.txt")
TUNED_LR_REPORT = os.path.join(RESULTS_DIR, "training_report_tuned_lr.txt")
TUNED_ANN_REPORT = os.path.join(RESULTS_DIR, "training_report_tuned_ann.txt")

SUMMARY_TXT = os.path.join(RESULTS_DIR, "model_comparison_summary.txt")
SUMMARY_CSV = os.path.join(RESULTS_DIR, "model_comparison_summary.csv")
RF_COMPARISON_PNG = os.path.join(RESULTS_DIR, "rf_baseline_vs_tuned.png")


@dataclass
class RunResult:
    name: str
    source_report: str
    test_macro_f1: float
    test_roc_auc: Optional[float]
    cv_best_f1: Optional[float] = None
    val_best_threshold: Optional[float] = None
    default_test_f1: Optional[float] = None
    tuned_test_f1: Optional[float] = None
    notes: str = ""


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_float(pattern: str, text: str, label: str, flags: int = 0) -> float:
    match = re.search(pattern, text, flags)
    if not match:
        raise ValueError(f"Could not find {label} in report")
    return float(match.group(1))


def try_extract_float(pattern: str, text: str, flags: int = 0) -> Optional[float]:
    match = re.search(pattern, text, flags)
    return float(match.group(1)) if match else None


def parse_baseline_rf(path: str) -> RunResult:
    text = read_text(path)

    # Baseline report stores the model comparison table and full per-model metrics.
    # We use the Random Forest row from the comparison table as the primary score.
    test_macro_f1 = extract_float(
        r"^Random Forest\s+([0-9.]+)\s+[0-9.]+$",
        text,
        "baseline RF F1",
        flags=re.MULTILINE,
    )
    test_roc_auc = extract_float(
        r"^Random Forest\s+[0-9.]+\s+([0-9.]+)$",
        text,
        "baseline RF ROC-AUC",
        flags=re.MULTILINE,
    )

    return RunResult(
        name="Baseline Random Forest",
        source_report=path,
        test_macro_f1=test_macro_f1,
        test_roc_auc=test_roc_auc,
        notes="Untuned baseline from script 8.",
    )


def parse_tuned_report(path: str, name: str, model_label: str) -> RunResult:
    text = read_text(path)

    cv_best_f1 = try_extract_float(r"Best CV F1\s*:\s*([0-9.]+)", text)
    val_best_threshold = try_extract_float(r"Best threshold\s*:\s*([0-9.]+)", text)

    default_test_f1 = try_extract_float(
        r"Macro-F1 @ threshold 0\.50\s*:\s*([0-9.]+)",
        text,
    )
    tuned_test_f1 = try_extract_float(
        r"Macro-F1 @ tuned threshold:\s*([0-9.]+)",
        text,
    )

    # Older scripts used slightly different spacing/labels, so we keep a fallback.
    if tuned_test_f1 is None:
        tuned_test_f1 = try_extract_float(r"Test macro-F1 @tuned\s*=\s*([0-9.]+)", text)
    if default_test_f1 is None:
        default_test_f1 = try_extract_float(r"Test macro-F1 @0\.50\s*=\s*([0-9.]+)", text)

    test_roc_auc = None
    roc = try_extract_float(r"ROC-AUC:\s*([0-9.]+)", text)
    if roc is not None:
        test_roc_auc = roc

    if tuned_test_f1 is None:
        raise ValueError(f"Could not find tuned test F1 in {path}")

    return RunResult(
        name=name,
        source_report=path,
        test_macro_f1=tuned_test_f1,
        test_roc_auc=test_roc_auc,
        cv_best_f1=cv_best_f1,
        val_best_threshold=val_best_threshold,
        default_test_f1=default_test_f1,
        tuned_test_f1=tuned_test_f1,
        notes=model_label,
    )


def write_csv(rows: list[RunResult], path: str) -> None:
    headers = [
        "name",
        "test_macro_f1",
        "test_roc_auc",
        "cv_best_f1",
        "val_best_threshold",
        "default_test_f1",
        "tuned_test_f1",
        "source_report",
        "notes",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for r in rows:
            values = [
                r.name,
                f"{r.test_macro_f1:.4f}",
                "" if r.test_roc_auc is None else f"{r.test_roc_auc:.4f}",
                "" if r.cv_best_f1 is None else f"{r.cv_best_f1:.4f}",
                "" if r.val_best_threshold is None else f"{r.val_best_threshold:.2f}",
                "" if r.default_test_f1 is None else f"{r.default_test_f1:.4f}",
                "" if r.tuned_test_f1 is None else f"{r.tuned_test_f1:.4f}",
                r.source_report,
                r.notes,
            ]
            f.write(",".join(f'"{v}"' for v in values) + "\n")


def main() -> None:
    runs = [
        parse_baseline_rf(BASELINE_REPORT),
        parse_tuned_report(TUNED_RF_REPORT, "Tuned Random Forest", "Random Forest tuned with RandomizedSearchCV"),
        parse_tuned_report(TUNED_LR_REPORT, "Tuned Logistic Regression", "Logistic Regression tuned with L1/L2"),
        parse_tuned_report(TUNED_ANN_REPORT, "Tuned ANN", "ANN tuned with MLPClassifier"),
    ]

    ranked = sorted(runs, key=lambda r: r.test_macro_f1, reverse=True)
    best = ranked[0]

    lines = []
    lines.append("ROOM USABILITY MODEL COMPARISON")
    lines.append("=" * 64)
    lines.append("")
    lines.append("Ranking criterion: final test macro-F1 from the saved run report")
    lines.append("")
    lines.append(f"{'Rank':<6}{'Model':<28}{'Test F1':>10}{'ROC-AUC':>10}{'CV F1':>10}{'Thresh':>10}")
    lines.append("-" * 74)

    for idx, r in enumerate(ranked, start=1):
        lines.append(
            f"{idx:<6}{r.name:<28}{r.test_macro_f1:>10.4f}"
            f"{'' if r.test_roc_auc is None else f'{r.test_roc_auc:>10.4f}'}"
            f"{'' if r.cv_best_f1 is None else f'{r.cv_best_f1:>10.4f}'}"
            f"{'' if r.val_best_threshold is None else f'{r.val_best_threshold:>10.2f}'}"
        )

    lines.append("")
    lines.append(f"Best observed run: {best.name} ({best.test_macro_f1:.4f} test macro-F1)")
    lines.append("")
    lines.append("Per-run notes:")
    for r in runs:
        lines.append(f"- {r.name}: {r.notes}")
        lines.append(f"  Source: {os.path.relpath(r.source_report, PROJECT_ROOT)}")
        if r.cv_best_f1 is not None:
            lines.append(f"  CV best macro-F1: {r.cv_best_f1:.4f}")
        if r.val_best_threshold is not None:
            lines.append(f"  Validation threshold: {r.val_best_threshold:.2f}")
        if r.default_test_f1 is not None:
            lines.append(f"  Test macro-F1 @0.50: {r.default_test_f1:.4f}")
        if r.tuned_test_f1 is not None:
            lines.append(f"  Test macro-F1 @tuned: {r.tuned_test_f1:.4f}")
        if r.test_roc_auc is not None:
            lines.append(f"  Test ROC-AUC: {r.test_roc_auc:.4f}")
        lines.append("")

    lines.append("Recommendation:")
    lines.append(
        "- If you want the highest reported test macro-F1 right now, keep the baseline Random Forest."
    )
    lines.append(
        "- If you want the strongest tuned candidate with a clean cross-validation search, the tuned Random Forest remains the best tuned model."
    )
    lines.append(
        "- Logistic Regression is a weaker but interpretable fallback; ANN is close to RF but does not clearly surpass it on the held-out test set."
    )

    summary_text = "\n".join(lines)
    with open(SUMMARY_TXT, "w", encoding="utf-8") as f:
        f.write(summary_text)

    write_csv(ranked, SUMMARY_CSV)

    # Produce a small comparison plot (Baseline RF vs Tuned RF)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        baseline = next(r for r in runs if r.name == "Baseline Random Forest")
        tuned = next(r for r in runs if r.name == "Tuned Random Forest")

        labels = ["Baseline RF", "Tuned RF"]
        f1_scores = [baseline.test_macro_f1, tuned.test_macro_f1]
        auc_scores = [baseline.test_roc_auc or 0.0, tuned.test_roc_auc or 0.0]

        x = list(range(len(labels)))
        width = 0.35

        fig, ax1 = plt.subplots(figsize=(6, 4))
        ax1.bar([i - width / 2 for i in x], f1_scores, width, label="Test macro-F1", color="#2b8cbe")
        ax1.set_ylabel("Test macro-F1")
        ax1.set_ylim(0, 1)
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels)

        ax2 = ax1.twinx()
        ax2.bar([i + width / 2 for i in x], auc_scores, width, label="ROC-AUC", color="#7bccc4")
        ax2.set_ylim(0, 1)
        ax2.set_ylabel("ROC-AUC")

        ax1.set_title("Random Forest: Baseline vs Tuned (Test set)")
        fig.legend(loc="upper right")
        plt.tight_layout()
        plt.savefig(RF_COMPARISON_PNG, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"RF comparison plot saved to {RF_COMPARISON_PNG}")
    except Exception as e:
        print(f"Could not create RF comparison plot: {e}")

    print(summary_text)
    print("")
    print(f"Summary written to {SUMMARY_TXT}")
    print(f"CSV written to {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
