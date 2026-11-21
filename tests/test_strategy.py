import numpy as np
import pandas as pd

from trendcarry.backtest import month_calendar, precompute, run, target_weights
from trendcarry.config import PRIMARY, VARIANTS, Params, Variant
from trendcarry.data import MarketData, align_rate
from trendcarry.portfolio import cap_gross, scale_to_target
from trendcarry.signals import carry_signal, trend_signal
from trendcarry.stats import dsr, expected_max_sharpe, psr

from .conftest import make_data

P = Params()


def test_trend_signal_sign():
    idx = pd.bdate_range("2020-01-01", periods=300)
    ex = pd.DataFrame({"up": 0.001, "down": -0.001, "short": 0.0}, index=idx)
    ex.loc[idx[-21:], "short"] = 0.002  # only the short lookback is positive; long ones too
    ex.loc[idx[:-21], "short"] = -0.002
    sig = trend_signal(ex, idx[-1], (21, 63, 252))
    assert sig["up"] == 1 and sig["down"] == -1
    assert sig["short"] == -1 / 3  # +1 (1m), -1 (3m), -1 (12m)


def test_trend_signal_needs_full_history():
    idx = pd.bdate_range("2020-01-01", periods=100)
    ex = pd.DataFrame({"a": 0.001}, index=idx)
    assert np.isnan(trend_signal(ex, idx[-1], (21, 63, 252))["a"])


def test_scale_to_target_hits_volatility():
    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.09]], index=["a", "b"], columns=["a", "b"])
    w = scale_to_target(pd.Series({"a": 1.0, "b": -2.0}), cov, 0.10)
    vol = np.sqrt(w.to_numpy() @ cov.to_numpy() @ w.to_numpy())
    assert abs(vol - 0.10) < 1e-12
    assert np.sign(w["a"]) == 1 and np.sign(w["b"]) == -1


def test_scale_drops_only_instruments_without_covariance():
    cov = pd.DataFrame([[0.04, np.nan], [np.nan, np.nan]], index=["a", "new"], columns=["a", "new"])
    w = scale_to_target(pd.Series({"a": 1.0, "new": 1.0}), cov, 0.10)
    assert list(w.index) == ["a"] and abs(w["a"] - 0.5) < 1e-12


def test_cap_gross():
    w = cap_gross(pd.Series({"a": 2.0, "b": -2.0}), 2.0)
    assert abs(w.abs().sum() - 2.0) < 1e-12


def test_carry_signal_modes():
    c = pd.DataFrame({"x": [0.01] * 12 + [0.03, -0.01]})
    hist = carry_signal(c, "hist_mean", 12)
    assert hist["x"].iloc[:11].isna().all()
    assert hist["x"].iloc[12] == 1 and hist["x"].iloc[13] == -1
    assert (carry_signal(c, "zero", 12)["x"].iloc[:12] == 1).all()


def test_align_rate_lag_and_staleness():
    idx = pd.bdate_range("2020-01-01", "2020-12-31")
    obs = pd.Series([0.01, 0.02], index=pd.to_datetime(["2020-01-06", "2020-02-03"]))
    s = align_rate(obs, idx, stale_days=93)
    assert np.isnan(s.loc["2020-01-03"])
    assert s.loc["2020-01-06"] == 0.01 and s.loc["2020-03-02"] == 0.02
    assert np.isnan(s.loc["2020-06-01"])  # stale


def test_month_calendar():
    idx = pd.bdate_range("2021-01-01", "2021-03-15")
    sig, exe = month_calendar(idx)
    assert exe[0] == pd.Timestamp("2021-01-29") and sig[0] == pd.Timestamp("2021-01-28")
    assert exe[-1] == pd.Timestamp("2021-03-15")


def test_no_lookahead(synthetic):
    """Changing every price after the signal date must not change the positions."""
    pre = precompute(synthetic, P)
    k = len(pre.exec_dates) - 30
    s = pre.signal_dates[k]
    base = run(pre, PRIMARY, P).weights.iloc[k]

    tr = synthetic.tr.copy()
    after = tr.index > s
    shock = np.random.default_rng(1).uniform(0.5, 1.5, (after.sum(), tr.shape[1]))
    tr.loc[after] = tr.loc[after] * shock
    rates = synthetic.rates.copy()
    rates.loc[after] = rates.loc[after] + 0.05
    changed = MarketData(tr=tr, close=tr, div=synthetic.div, rates=rates)
    pre2 = precompute(changed, P)
    w2 = run(pre2, PRIMARY, P).weights.iloc[k]
    pd.testing.assert_series_equal(base, w2, check_names=False)


def test_backtest_runs_and_targets_vol(synthetic):
    pre = precompute(synthetic, P)
    for v in VARIANTS:
        res = run(pre, v, P)
        assert len(res.returns) > 60
        assert np.isfinite(res.returns).all()
    res = run(pre, PRIMARY, P)
    realized = res.gross_returns.std() * np.sqrt(12)
    assert 0.05 < realized < 0.20  # ex-ante target 10 %


def test_trend_profits_from_persistent_trends():
    data = make_data(seed=3, drift={"SPY": 0.002, "TLT": -0.002, "GLD": 0.002})
    pre = precompute(data, P)
    res = run(pre, Variant("trend", carry=False), P)
    assert res.returns.mean() > 0
    w = res.weights.iloc[-2]
    assert w["SPY"] > 0 and w["TLT"] < 0 and w["GLD"] > 0


def test_implementable_respects_gross_cap(synthetic):
    pre = precompute(synthetic, P)
    res = run(pre, Variant("impl", implementable=True), P)
    assert (res.weights.abs().sum(axis=1) <= P.max_gross + 1e-9).all()


def test_psr_dsr():
    rng = np.random.default_rng(0)
    noise = pd.Series(rng.normal(0, 0.03, 600))
    assert 0.0 < psr(noise - noise.mean()) < 1.0
    assert abs(psr(noise - noise.mean()) - 0.5) < 1e-9
    good = noise + 0.01
    assert psr(good) > 0.99
    srs = [0.05, 0.1, 0.2, 0.3, 0.15, 0.25]
    assert expected_max_sharpe(srs, 50) > expected_max_sharpe(srs, 6) > 0
    assert dsr(good, srs, 6) <= psr(good)
