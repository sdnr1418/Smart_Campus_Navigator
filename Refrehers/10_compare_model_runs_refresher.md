# Refresher: `10_compare_model_runs.py`
### Smart Campus Navigator — Model Comparison Utility

---

## TL;DR (30-second summary)
Script 10 is an automated reporting utility. Instead of you having to manually open 4 different `.txt` files to figure out which machine learning model performed the best, this script does it for you. 
It uses Regular Expressions (Regex) to read the reports, extracts the key metrics, and builds a consolidated leaderboard.

---

## File I/O

```
READS (Input Reports):
  Results/training_report.txt              ← Baseline models (from Script 8)
  Results/training_report_tuned_rf.txt     ← Tuned Random Forest (from Script 9)
  Results/training_report_tuned_lr.txt     ← Tuned Logistic Regression
  Results/training_report_tuned_ann.txt    ← Tuned Neural Network

WRITES (Consolidated Outputs):
  Results/model_comparison_summary.txt     ← A ranked text leaderboard
  Results/model_comparison_summary.csv     ← The same leaderboard in CSV format
  Results/rf_baseline_vs_tuned.png         ← A bar chart comparing Baseline RF vs Tuned RF
```

---

## 1. How It Reads The Reports (Regex Parsing)

The script uses Python's `re` (Regular Expression) module to scan through the raw text of the training reports. 

For example, to find the "Best threshold" in the Tuned RF report, it looks for the string pattern:
```python
r"Best threshold\s*:\s*([0-9.]+)"
```
This tells Python: *"Look for the words 'Best threshold', followed by any spaces, a colon, and grab the decimal number right after it."*

It extracts the following metrics for each model:
* **Test Macro-F1** (The primary metric used for ranking)
* **Test ROC-AUC**
* **CV Best F1**
* **Validation Best Threshold**

---

## 2. Generating the Leaderboard

Once it extracts the data into `RunResult` data classes, it sorts them by `test_macro_f1` in descending order:
```python
ranked = sorted(runs, key=lambda r: r.test_macro_f1, reverse=True)
```

It then formats these into a clean, alignment-spaced text table.

```text
ROOM USABILITY MODEL COMPARISON
================================================================
Ranking criterion: final test macro-F1 from the saved run report

Rank  Model                       Test F1   ROC-AUC     CV F1    Thresh
--------------------------------------------------------------------------
1     Tuned Random Forest          0.9324    0.9834    0.9340      0.52
2     Baseline Random Forest       0.9328    0.9834                    
3     Tuned ANN                    0.9183    0.9818                    
4     Tuned Logistic Regression    0.8581    0.9601                    
```

---

## 3. Visualisation (Matplotlib Bar Chart)

Finally, it specifically pulls out the **Baseline Random Forest** and the **Tuned Random Forest** to create a direct comparison.

It uses `matplotlib` to plot a dual-axis bar chart (`rf_baseline_vs_tuned.png`). 
* The **left Y-axis** plots the `Test macro-F1` score.
* The **right Y-axis** (created using `ax1.twinx()`) plots the `ROC-AUC` score.

This PNG provides an immediate visual summary for your project report to prove whether hyperparameter tuning actually improved the model or if the default settings were already optimal.

---

## Why Script 10 is Built This Way
* **Automation:** If you decide to change the dataset in Script 7, you just run Scripts 8, 9, and 10 in sequence. You instantly get an updated, formatted leaderboard without doing any manual data entry.
* **Traceability:** It keeps a programmatic record of exactly which model is currently the best, ensuring you always deploy the correct one to Streamlit.
