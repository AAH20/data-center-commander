"""TDD: Evolutionary correlation analytics test - RED phase expected XFAIL"""


def test_compute_correlation_metrics_structure():
    """Test compute_correlation_metrics returns expected dict structure.

    RED phase: Test should FAIL when called with bad data, but function exists.
    """
    from improvements.evolutionary_correlation import compute_correlation_metrics

    # Test with valid data
    alerts = [
        {"nodes": ["A", "B"], "ioc_score": 0.8, "severity": "high", "ground_truth": True},
        {"nodes": ["B", "C"], "ioc_score": 0.6, "severity": "medium", "ground_truth": False},
    ]
    result = compute_correlation_metrics(alerts)
    assert "precision" in result
    assert "recall" in result
    assert "f1" in result
    assert "true_positives" in result
    assert "false_positives" in result
    assert "false_negatives" in result


def test_generate_evolutionary_correlation_report_structure():
    """Test generate_evolutionary_correlation_report returns formatted string."""
    from improvements.evolutionary_correlation import generate_evolutionary_correlation_report

    alerts = [
        {"nodes": ["A", "B"], "ioc_score": 0.8, "severity": "high", "ground_truth": True},
        {"nodes": ["B", "C"], "ioc_score": 0.6, "severity": "medium", "ground_truth": False},
    ]
    report = generate_evolutionary_correlation_report(alerts)
    assert isinstance(report, str)
    assert "Evolutionary Correlation" in report or "Correlation" in report
