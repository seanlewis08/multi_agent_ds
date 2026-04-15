# Ground Truth Feature Importance — Expected Model Answers

## Overview

The synthetic dataset is generated using a **logistic regression ground truth function** with known coefficients, categorical mappings, interaction terms, and Gaussian noise. This document describes the exact data-generating process (DGP) and what a well-trained model should recover in terms of feature importance.

**Target column:** `binary_target`  
**Target rate:** ~27%  
**True probability range:** [~0.02, ~0.90]  
**Noise:** Gaussian noise (σ = 0.5) added to the logit before sampling the binary label  

---

## 1. The Ground Truth Function

```
logit = INTERCEPT
      + Σ (coef_i × feature_i)           # main effects (numeric)
      + Σ (map_j(category_j))            # main effects (categorical)
      + Σ (coef_k × feat_a_k × feat_b_k) # interaction terms

P(target=1) = sigmoid(logit)

label ~ Bernoulli(sigmoid(logit + ε)),  ε ~ N(0, 0.5)
```

**Intercept:** −1.97

---

## 2. Main Effects — Numeric Features

| Feature | Coefficient | Range (min–max) | Logit Span¹ | Direction | Domain Rationale |
|---|---|---|---|---|---|
| `num_prior_claims` | **+0.077** | 0–12 | **0.924** | ↑ more claims → higher risk | Strongest signal; direct claims history |
| `credit_score` | **−0.00213** | 300–850 | **1.172** | ↓ higher credit → lower risk | Wide range amplifies moderate coef |
| `age` | +0.0086 | 16–85 | 0.593 | ↑ older → higher risk | Older drivers accumulate risk |
| `annual_income` | −0.0000035 | 15k–250k | 0.823 | ↓ higher income → lower risk | Financial stability proxy |
| `claim_amount_avg` | +0.0000128 | 0–50k | 0.640 | ↑ larger past claims → higher risk | Severity history |
| `vehicle_value` | +0.0000065 | 2k–80k | 0.507 | ↑ expensive vehicle → higher risk | Higher replacement cost |
| `policy_tenure_months` | −0.0017 | 1–240 | 0.406 | ↓ longer tenure → lower risk | Loyalty / stability signal |
| `annual_premium` | +0.000086 | 400–8k | 0.653 | ↑ higher premium → higher risk | Risk-tier proxy |
| `miles_driven_annual` | +0.0000086 | 1k–50k | 0.421 | ↑ more miles → more exposure | Exposure measure |
| `distance_to_work` | +0.00341 | 0.5–80 | 0.271 | ↑ longer commute → more exposure | Daily exposure proxy |
| `num_vehicles` | +0.042 | 1–6 | 0.210 | ↑ more vehicles → more exposure | Fleet size |
| `num_drivers_on_policy` | +0.035 | 1–5 | 0.140 | ↑ more drivers → more risk | Multi-driver risk |

¹ **Logit Span** = |coefficient × (max − min)|. This measures the total range of logit contribution a feature can produce. Larger span → more potential influence on the predicted probability.

---

## 3. Main Effects — Categorical Features

Each categorical feature contributes a fixed logit offset per level. The **total span** (max level value − min level value) determines its discriminative power.

| Feature | Levels | Logit Span | Strongest Positive | Strongest Negative |
|---|---|---|---|---|
| `state` | 10 | 0.150 | FL (+0.108) | OH (−0.042) |
| `coverage_tier` | 4 | 0.151 | liability_only (+0.086) | premium (−0.065) |
| `marital_status` | 4 | 0.107 | single (+0.065) | married (−0.042) |
| `vehicle_type` | 6 | 0.088 | truck (+0.065) | hatchback/van (−0.023) |
| `education_level` | 5 | 0.084 | high_school (+0.042) | doctorate (−0.042) |

---

## 4. Interaction Terms

These are **non-additive** effects — the risk contribution of one feature depends on the value of another. Tree-based models (GBM) can discover these naturally; logistic regression cannot without explicit feature engineering.

| Interaction | Coefficient | Interpretation |
|---|---|---|
| `age × num_prior_claims` | −0.0012 | **Younger** drivers with many prior claims are disproportionately risky. (Negative coef means low age + high claims → higher logit since age is low.) |
| `num_prior_claims × claim_amount_avg` | +0.0000025 | Many claims **and** high average claim amounts compound risk. |
| `credit_score × vehicle_value` | +0.0000000035 | High vehicle value with low credit → overextended → higher risk. (Small coef, but wide ranges: 300–850 × 2k–80k.) |
| `miles_driven_annual × num_vehicles` | +0.0000004 | More miles **and** more vehicles → multiplicative exposure. |

---

## 5. Expected Feature Importance Rankings

### 5a. Logistic Regression

A logistic regression model fits *exactly* the same functional form as the DGP (sigmoid of linear combination), so it should recover the ground truth almost perfectly.

**Expected coefficient ranking by absolute logit span (largest → smallest):**

| Rank | Feature | Approx. Logit Span |
|---|---|---|
| 1 | `credit_score` | 1.17 |
| 2 | `num_prior_claims` | 0.92 |
| 3 | `annual_income` | 0.82 |
| 4 | `annual_premium` | 0.65 |
| 5 | `claim_amount_avg` | 0.64 |
| 6 | `age` | 0.59 |
| 7 | `vehicle_value` | 0.51 |
| 8 | `miles_driven_annual` | 0.42 |
| 9 | `policy_tenure_months` | 0.41 |
| 10 | `distance_to_work` | 0.27 |
| 11 | `num_vehicles` | 0.21 |
| 12 | `state` | 0.15 |
| 13 | `coverage_tier` | 0.15 |
| 14 | `num_drivers_on_policy` | 0.14 |
| 15 | `marital_status` | 0.11 |
| 16 | `vehicle_type` | 0.09 |
| 17 | `education_level` | 0.08 |

**Key expectations for logistic regression:**
- Recovered coefficients should closely match the ground truth values (within noise).
- The interaction terms **will not be discovered** unless interaction features are explicitly engineered (e.g., `age × num_prior_claims`).
- The noise (σ = 0.5) limits the Bayes-optimal AUC; a perfect logistic model cannot achieve AUC = 1.0.
- Categorical features will require one-hot encoding; individual dummy coefficients should match the `CATEGORICAL_MAPS` values.

---

### 5b. Gradient Boosted Machine (GBM / LightGBM)

A GBM does **not** directly recover logistic regression coefficients. Instead, it uses tree splits and reports importance via split-based gain or permutation importance. Key differences:

**Expected importance ranking (by gain):**

| Tier | Features | Why |
|---|---|---|
| **Top tier** | `credit_score`, `num_prior_claims`, `annual_income` | Largest logit spans; `num_prior_claims` also participates in 2 interactions |
| **High tier** | `claim_amount_avg`, `age`, `annual_premium`, `vehicle_value` | Moderate logit spans; `age`, `claim_amount_avg`, `vehicle_value` each participate in an interaction |
| **Mid tier** | `miles_driven_annual`, `policy_tenure_months` | Moderate main effects; `miles_driven_annual` has an interaction with `num_vehicles` |
| **Lower tier** | `distance_to_work`, `num_vehicles`, `num_drivers_on_policy` | Smaller logit spans; `num_vehicles` boosted slightly by interaction |
| **Lowest tier** | `state`, `coverage_tier`, `marital_status`, `vehicle_type`, `education_level` | Small categorical effects; many levels dilute per-split gain |

**Key expectations for GBM:**

1. **Interactions will be discovered automatically.** The GBM will find that `num_prior_claims` is more predictive when `age` is low or when `claim_amount_avg` is high. This means features involved in interactions may rank *higher* in GBM importance than their pure main-effect span would suggest.

2. **`num_prior_claims` will likely be #1 or #2.** It has a strong main effect (0.077 per unit, up to 12 units) AND participates in two interactions, making it the most split-worthy feature.

3. **`credit_score` will be #1 or #2.** Largest absolute logit span among all features, plus an interaction with `vehicle_value`.

4. **Categorical features will rank lower than numerics.** With uniform distributions and small logit offsets (0.02–0.10), categories provide less gain per split than the wide-range numerics.

5. **GBM gain importance is *not* proportional to logit coefficients.** GBM importance reflects how much a feature reduces loss across all splits. Features with wide ranges and/or interactions accumulate more gain.

6. **Permutation importance** will more closely align with the logit span ranking because it measures the total predictive contribution removed.

---

## 6. Expected Model Performance

| Metric | Approximate Expected Value | Notes |
|---|---|---|
| **AUC-ROC** | 0.78–0.85 | Limited by the noise (σ = 0.5) added to the logit |
| **Gini** | 0.56–0.70 | = 2 × AUC − 1 |
| **Target rate** | ~27% | Moderate imbalance |
| **True prob range** | [~0.02, ~0.90] | Good discrimination range |

**Why not AUC = 1.0?**  
The label is sampled stochastically: even knowing the true probability, the Bernoulli draw adds irreducible noise. The logit noise (σ = 0.5) further blurs the decision boundary.

---

## 7. Summary of Directions

A quick reference for sign-checking model outputs:

| Feature | Direction | Coefficient Sign |
|---|---|---|
| `age` | ↑ older → higher risk | + |
| `annual_income` | ↑ higher income → lower risk | − |
| `credit_score` | ↑ higher credit → lower risk | − |
| `vehicle_value` | ↑ more expensive → higher risk | + |
| `annual_premium` | ↑ higher premium → higher risk | + |
| `claim_amount_avg` | ↑ larger claims → higher risk | + |
| `miles_driven_annual` | ↑ more miles → higher risk | + |
| `distance_to_work` | ↑ longer commute → higher risk | + |
| `num_prior_claims` | ↑ more claims → higher risk | + |
| `policy_tenure_months` | ↑ longer tenure → lower risk | − |
| `num_vehicles` | ↑ more vehicles → higher risk | + |
| `num_drivers_on_policy` | ↑ more drivers → higher risk | + |

---

*Document generated from `src/multi_agent_ds/tools/data_generator.py` ground truth constants.*  
*Last updated: April 14, 2026*

