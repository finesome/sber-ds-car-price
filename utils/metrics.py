import numpy as np

def mape(y_true, y_pred, **kwargs):
    return np.mean(np.abs((y_pred - y_true) / y_true))