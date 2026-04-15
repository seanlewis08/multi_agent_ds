import numpy as np
from pandas import Series
from sklearn.metrics import roc_auc_score

def ase(
    y_true: Series,
    y_pred: Series,
    sample_weight: Series,
) -> float:
    y_bar = np.sum(sample_weight * y_true) / np.sum(sample_weight)

    result = (100 / y_bar) ** 2 * (
        np.sum(sample_weight * (y_true - y_pred) ** 2) / np.sum(sample_weight)
        - np.sum(sample_weight * (y_true - y_bar) ** 2) / np.sum(sample_weight)
    )
    return result


def gini(
    y_true: Series,
    y_pred: Series,
) -> float:
    target = np.asarray(y_true)
    prediction = np.asarray(y_pred)
    unique_targets = np.unique(target)
    if unique_targets.size < 2:
        raise ValueError("GINI requires at least two target classes.")
    return 2.0 * roc_auc_score(target, prediction) - 1.0
