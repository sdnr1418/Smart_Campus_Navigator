# Refresher: `9_tune_random_forest.py`
### Smart Campus Navigator — Random Forest Hyperparameter Tuning

---

## TL;DR (30-second summary)
Script 8 trained 3 models with **default settings** to find the best *type* of model (Random Forest won).
Script 9 takes that winner and asks: **"What are the best *settings* for this Random Forest?"**
It also introduces a second improvement — tuning the **decision threshold** to squeeze out better predictions.

---

## File I/O

```
READS:
  Data/room_usability_dataset.csv           ← same dataset from Script 7

WRITES:
  Models/room_usability_model_tuned_rf.pkl  ← tuned model (replaces the basic one)
  Results/training_report_tuned_rf.txt      ← detailed tuning report
  Results/confusion_matrix_tuned_rf.png     ← side-by-side CM: default vs tuned threshold
```

### What's inside the saved `.pkl` bundle?

| Key | Type | Description |
|-----|------|-------------|
| `model` | RF estimator | The final tuned Random Forest object |
| `model_name` | String | `"Random Forest (Tuned)"` |
| `feature_cols` | List[str] | The 19 features in exact order (same as Script 8) |
| `threshold` | Float | The best decision threshold found (e.g., `0.42`) |
| `best_params` | Dict | The winning hyperparameter combination |
| `cv_best_f1_macro` | Float | Best cross-validation F1-macro score |

> **Why is `threshold` saved?** Unlike Script 8 (which used 0.5 always), this model needs its custom threshold to reproduce the same predictions in production.

---

## The 3-Way Data Split: 60 / 20 / 20

Script 8 used a simple 80/20 split. Script 9 needs **three** separate sets:

```python
# Step 1: Hold out 20% as test (never touched during tuning)
X_trainval, X_test = train_test_split(X, y, test_size=0.2, stratify=y)

# Step 2: Split remaining 80% into 60% train + 20% validation
X_train, X_val = train_test_split(X_trainval, y_trainval, test_size=0.25, stratify=y_trainval)
# Note: 0.25 × 80% = 20% of total dataset
```

| Split | Size | Purpose |
|-------|------|---------|
| **Train (60%)** | Majority of data | Fitting the model during cross-validation |
| **Validation (20%)** | Held-out during CV | Tuning the decision threshold |
| **Test (20%)** | Completely untouched | Final honest evaluation |

**Why three splits instead of two?**
- Threshold tuning is a form of optimization. If you tune threshold on the test set, you're "peeking" at it — the test score becomes optimistic and misleading.
- The validation set is used for threshold tuning, keeping the test set truly unseen.

---

## Stage 1: RandomizedSearchCV — Finding the Best Hyperparameters

### The Search Space (7 hyperparameters, 40 random combinations tried)

```python
param_dist = {
    "n_estimators":      [100, 200, 300, 500, 800],   # Number of trees
    "max_depth":         [None, 10, 15, 20, 30],       # Max tree depth (None = unlimited)
    "min_samples_split": [2, 5, 10, 20],               # Min samples to split a node
    "min_samples_leaf":  [1, 2, 4, 8],                 # Min samples at a leaf node
    "max_features":      ["sqrt", "log2", 0.5, 0.7, 1.0], # Features considered per split
    "class_weight":      [None, "balanced", "balanced_subsample"],
    "bootstrap":         [True, False],
}
```

### What each hyperparameter controls:

| Parameter | Effect of increasing | Effect of decreasing |
|-----------|---------------------|---------------------|
| `n_estimators` | More stable, slower | Faster, noisier |
| `max_depth` | More complex, risk overfitting | Simpler, might underfit |
| `min_samples_split` | Simpler tree (less splits) | More splits, more detail |
| `min_samples_leaf` | Smoother predictions | More sensitive to local patterns |
| `max_features` | Considers more features per split | More randomness, less correlation between trees |
| `class_weight="balanced"` | Penalises errors on minority class more | Equal penalty for both classes |
| `bootstrap=False` | Each tree sees all data | Each tree sees random sample |

### Why RandomizedSearch instead of GridSearch?

**GridSearch** tries every single combination. With this search space:
```
5 × 5 × 4 × 4 × 5 × 3 × 2 = 12,000 combinations × 5-fold CV = 60,000 model fits!
```

**RandomizedSearch** randomly samples 40 combinations × 5-fold CV = 200 model fits.

Result: ~300x faster with typically >95% of the quality. The best hyperparameter combination is rarely found at the extremes of the grid.

### 5-Fold Cross Validation (happening inside the search)

For each of the 40 random hyperparameter combos:
```
Full training data (60%) split into 5 equal folds:

Fold 1: [VAL] [TRN] [TRN] [TRN] [TRN] → F1 score
Fold 2: [TRN] [VAL] [TRN] [TRN] [TRN] → F1 score
Fold 3: [TRN] [TRN] [VAL] [TRN] [TRN] → F1 score
Fold 4: [TRN] [TRN] [TRN] [VAL] [TRN] → F1 score
Fold 5: [TRN] [TRN] [TRN] [TRN] [VAL] → F1 score

Average F1 → this combo's score
```

This gives a **robust estimate** of how the model performs on unseen data — much better than a single train/test evaluation.

### `refit=True` — What it means
After finding the best combo, `RandomizedSearchCV` automatically **retrains** the model on the **full training set** (all 5 folds combined) using those best parameters. This is the model stored in `search.best_estimator_`.

---

## Stage 2: Threshold Tuning — Finding the Best Decision Boundary

### The Default (Script 8 approach)
```
Model outputs probability: P(usable) = 0.43
Default threshold = 0.50
Decision: 0.43 < 0.50 → Predict "Not Usable"
```

### The Problem with Always Using 0.5
The default threshold assumes that FP (false alarm: "room is free" but it's busy) and FN (missed opportunity: "room is busy" but it's actually free) are equally bad. But for this app:
- **FP is worse** — a student walks to a room and finds it occupied. Very frustrating.
- **FN is fine** — the student simply doesn't get a recommendation. Minor inconvenience.

By adjusting the threshold **up** (e.g., to 0.6), the model becomes more conservative — it only recommends a room when it's quite confident it's usable. Fewer FPs, more FNs.
By adjusting the threshold **down** (e.g., to 0.4), it recommends more rooms — fewer missed opportunities but more false alarms.

### The Search (81 threshold values, 0.1 to 0.9)

```python
def find_best_threshold(y_true, y_prob):
    best_threshold = 0.5
    best_f1 = -1.0

    for t in np.linspace(0.1, 0.9, 81):          # 81 evenly spaced values
        y_pred = (y_prob >= t).astype(int)         # Apply this threshold
        score = f1_score(y_true, y_pred, average="macro")
        if score > best_f1:
            best_f1 = score
            best_threshold = float(t)

    return best_threshold, best_f1
```

**Example threshold sweep:**
```
t=0.30: F1=0.782  (too many false positives)
t=0.40: F1=0.801
t=0.45: F1=0.814  ← improving
t=0.50: F1=0.809  (default — not optimal!)
t=0.55: F1=0.818  ← best found
t=0.60: F1=0.805
t=0.70: F1=0.773  (too conservative)
```

The best threshold is found on the **validation set** (not test set) to avoid peeking.

---

## Stage 3: Final Refit on Train+Val, Evaluate on Test

```python
# Refit on 80% of data (train + val combined) using the best hyperparameters
best_rf_final = RandomForestClassifier(**best_params, random_state=42, n_jobs=-1)
best_rf_final.fit(X_trainval, y_trainval)   # X_trainval = train + val

# Evaluate on the completely untouched 20% test set
y_prob_test = best_rf_final.predict_proba(X_test)[:, 1]
y_pred_test_tuned   = (y_prob_test >= best_threshold).astype(int)  # with tuned threshold
y_pred_test_default = (y_prob_test >= 0.50).astype(int)            # with default threshold
```

**Why refit on train+val combined?**
More data → better model. The validation set was only used for threshold selection, not for finding hyperparameters. So it's safe to include it in the final training.

---

## Output: Confusion Matrix Plot

The saved PNG shows **two** side-by-side confusion matrices on the test set:

```
┌─────────────────────┐   ┌─────────────────────┐
│  Threshold = 0.50   │   │  Threshold = 0.55    │
│  (default)          │   │  (tuned)             │
│                     │   │                      │
│  F1 = 0.809         │   │  F1 = 0.818  ← Better│
└─────────────────────┘   └─────────────────────┘
```

This visual directly shows the impact of threshold tuning — usually fewer False Positives (top-right cell gets smaller).

---

## How Script 9 Differs from Script 8

| Aspect | Script 8 | Script 9 |
|--------|----------|----------|
| Goal | Find the best *model type* | Find the best *model settings* |
| Models trained | LR + RF + ANN | RF only (already chosen as winner) |
| Hyperparameters | Defaults only | 40 random combinations searched |
| Data split | 80/20 | 60/20/20 |
| Threshold | Always 0.5 | Optimised on validation set |
| Saved bundle | model + feature_cols | model + feature_cols + **threshold** + best_params |

---

## Full Execution Flow

```
[1] Load CSV → 60/20/20 stratified 3-way split
[2] RandomizedSearchCV (40 combos × 5-fold CV) on train set
    → Best hyperparameters + best CV F1
[3] Predict probabilities on validation set
    → Sweep thresholds 0.1 to 0.9 → Best threshold
[4] Refit best RF on train+val combined
    → Evaluate with BOTH thresholds on test set
[5] Save model bundle (.pkl with threshold included)
[6] Save report (.txt) + confusion matrix plot (.png)
```

---

## Quick Reference

| Parameter | Value | Why |
|-----------|-------|-----|
| Search iterations | 40 | ~300x faster than full grid (12,000 combos) |
| CV folds | 5 | Standard — robust estimate with 60% training data |
| Scoring metric | `f1_macro` | Balances performance on both classes |
| Threshold sweep | 0.1 → 0.9 (81 steps) | Fine-grained search in 0.01 increments |
| Threshold tuned on | Validation set (20%) | Keeps test set completely uncontaminated |
| Final fit data | Train + Val (80%) | Maximises data for the deployed model |
