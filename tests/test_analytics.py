import pytest
from datetime import date

from treasury_data_engine import compute_2s10s, compute_zscore


def test_compute_2s10s_positive():
    assert compute_2s10s(1.23, 2.34) == round(2.34 - 1.23, 4)


def test_compute_2s10s_negative():
    assert compute_2s10s(3.0, 2.0) == round(2.0 - 3.0, 4)


def test_compute_zscore_insufficient():
    assert compute_zscore([], 0) == 0
    assert compute_zscore([1.0], 1.0) == 0


def test_compute_zscore_zero_std():
    vals = [2.0, 2.0, 2.0]
    assert compute_zscore(vals, 2.0) == 0


def test_compute_zscore_normal():
    vals = [1.0, 2.0, 3.0, 4.0]
    latest = vals[-1]
    # manual compute
    import statistics

    mean = statistics.mean(vals)
    std = statistics.stdev(vals)
    expected = round((latest - mean) / std, 4)
    assert compute_zscore(vals, latest) == expected
