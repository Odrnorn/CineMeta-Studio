from cinemeta.domain.confidence_logic import AmpelStatus, classify


def test_green_clear_winner():
    opts = [{"label": "A", "score": 0.92}, {"label": "B", "score": 0.70}]
    r = classify(opts)
    assert r.status == AmpelStatus.GREEN
    assert r.best["label"] == "A"


def test_yellow_close_scores():
    opts = [{"label": "A", "score": 0.88}, {"label": "B", "score": 0.85}]
    r = classify(opts)
    assert r.status == AmpelStatus.YELLOW


def test_red_low_score():
    opts = [{"label": "A", "score": 0.40}, {"label": "B", "score": 0.30}]
    r = classify(opts)
    assert r.status == AmpelStatus.RED


def test_red_empty_options():
    r = classify([])
    assert r.status == AmpelStatus.RED
    assert r.best is None


def test_single_option_above_threshold():
    opts = [{"label": "X", "score": 0.95}]
    r = classify(opts)
    # distance == best_score (no second option) → >= 0.15 → GREEN
    assert r.status == AmpelStatus.GREEN


def test_distance_calculated_correctly():
    opts = [{"label": "A", "score": 0.80}, {"label": "B", "score": 0.60}]
    r = classify(opts)
    assert abs(r.distance - 0.20) < 1e-9
