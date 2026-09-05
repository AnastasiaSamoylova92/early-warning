# Tests for deterministic EWS risk queries

import pandas as pd
import pytest
import numpy as np

from app.config import DATABASE_PATH
from app.data.repository import (
    RiskDataNotFoundError,
    RiskRepository)


@pytest.fixture(scope="module")
def repository() -> RiskRepository:
    """Return a repository connected to the local test database."""

    return RiskRepository(DATABASE_PATH)


def test_region_risk_summary_covers_current_snapshot(
    repository: RiskRepository,
) -> None:
    """Regional summary should cover the complete current snapshot."""

    result = repository.get_current_risk_by_region()

    assert len(result) == 10
    assert result["evaluated_product_count"].sum() == 2_000
    assert result["high_risk_product_count"].sum() == 123
    assert result["target_month"].nunique() == 1
    assert result["high_risk_rate_pct"].between(0, 100).all()


def test_region_risk_summary_has_deterministic_order(
    repository: RiskRepository,
) -> None:
    """Regional results should follow the documented ordering."""

    result = repository.get_current_risk_by_region()

    expected = (
        result
        .sort_values(
            by=[
                "high_risk_product_count",
                "high_risk_revenue_exposure",
                "region_id",
            ],
            ascending=[False, False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        result.reset_index(drop=True),
        expected,
    )

def test_current_low_to_high_transitions(
    repository: RiskRepository,
) -> None:
    """Current Low-to-High transitions should compare consecutive months."""

    result = repository.get_current_risk_transitions(
        from_level="low",
        to_level="high",
        n=100,
    )

    assert not result.empty

    assert result[
        "previous_predicted_risk_label"
    ].eq("Low Risk").all()

    assert result[
        "current_predicted_risk_label"
    ].eq("High Risk").all()

    expected_probability_change = (
        result["current_high_risk_probability"]
        - result["previous_high_risk_probability"]
    )

    assert np.allclose(
        result["high_risk_probability_change"],
        expected_probability_change,
    )

    expected_current_month = (
        result["previous_target_month"]
        + pd.offsets.MonthBegin(1)
    )

    pd.testing.assert_series_equal(
        result["current_target_month"].reset_index(drop=True),
        expected_current_month.reset_index(drop=True),
        check_names=False,
    )


def test_current_risk_transitions_have_deterministic_order(
    repository: RiskRepository,
) -> None:
    """Transitions should follow the documented ranking rules."""

    result = repository.get_current_risk_transitions(
        from_level="low",
        to_level="high",
        n=100,
    )

    expected = (
        result
        .sort_values(
            by=[
                "high_risk_probability_change",
                "current_high_risk_probability",
                "product_id",
                "region_id",
            ],
            ascending=[False, False, True, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        result.reset_index(drop=True),
        expected,
    )

def test_three_month_revenue_declines_are_strictly_decreasing(
    repository: RiskRepository,
) -> None:
    """Returned revenue series should contain three strict declines."""

    result = repository.get_current_three_month_revenue_declines(
        n=100
    )

    assert not result.empty

    assert (
        result["revenue_3m_ago"]
        > result["revenue_2m_ago"]
    ).all()

    assert (
        result["revenue_2m_ago"]
        > result["revenue_1m_ago"]
    ).all()

    assert (
        result["revenue_1m_ago"]
        > result["current_revenue"]
    ).all()

def test_product_risk_drivers_return_requested_number(
    repository: RiskRepository,
) -> None:
    """The repository should return the requested driver count."""

    product_region = (
        repository
        .get_top_risk_product_regions(1)
        .iloc[0]
    )

    result = repository.get_product_risk_drivers(
        product_id=int(product_region["product_id"]),
        region_id=int(product_region["region_id"]),
        n=3,
    )

    assert len(result) == 3


def test_product_risk_drivers_are_ordered_by_rank(
    repository: RiskRepository,
) -> None:
    """Local model drivers should be returned in rank order."""

    product_region = (
        repository
        .get_top_risk_product_regions(1)
        .iloc[0]
    )

    result = repository.get_product_risk_drivers(
        product_id=int(product_region["product_id"]),
        region_id=int(product_region["region_id"]),
    )

    assert result["driver_rank"].tolist() == [1, 2, 3, 4, 5]


def test_product_risk_drivers_include_business_context(
    repository: RiskRepository,
) -> None:
    """Technical drivers should be accompanied by business context."""

    product_region = (
        repository
        .get_top_risk_product_regions(1)
        .iloc[0]
    )

    result = repository.get_product_risk_drivers(
        product_id=int(product_region["product_id"]),
        region_id=int(product_region["region_id"]),
    )

    expected_columns = {
        "business_risk_indicators",
        "recommended_action",
        "predicted_risk_label",
        "high_risk_probability",
        "feature",
        "feature_label",
        "explained_class_contribution_percentage_points",
        "high_risk_contribution_percentage_points",
    }

    assert expected_columns.issubset(result.columns)


def test_product_risk_drivers_match_predicted_class(
    repository: RiskRepository,
) -> None:
    """The explained class should match the current prediction."""

    product_region = (
        repository
        .get_top_risk_product_regions(1)
        .iloc[0]
    )

    result = repository.get_product_risk_drivers(
        product_id=int(product_region["product_id"]),
        region_id=int(product_region["region_id"]),
    )

    assert (
        result["explained_class"]
        == result["predicted_risk_label"]
    ).all()


def test_high_risk_contribution_percentage_points(
    repository: RiskRepository,
) -> None:
    """High-risk probability contributions should use percentage points."""

    product_region = (
        repository
        .get_top_risk_product_regions(1)
        .iloc[0]
    )

    result = repository.get_product_risk_drivers(
        product_id=int(product_region["product_id"]),
        region_id=int(product_region["region_id"]),
    )

    expected_percentage_points = (
        result["contribution_to_high_risk_probability"]
        * 100
    )

    assert np.allclose(
        result["high_risk_contribution_percentage_points"],
        expected_percentage_points,
    )


def test_product_risk_drivers_raise_for_missing_data(
    repository: RiskRepository,
) -> None:
    """Unknown product-region combinations should raise an error."""

    with pytest.raises(
        RiskDataNotFoundError,
        match="No current model contributions found",
    ):
        repository.get_product_risk_drivers(
            product_id=999_999,
            region_id=999,
        )


@pytest.mark.parametrize("n", [0, 6])
def test_product_risk_drivers_reject_invalid_limit(
    repository: RiskRepository,
    n: int,
) -> None:
    """Driver limits outside one through five should be rejected."""

    product_region = (
        repository
        .get_top_risk_product_regions(1)
        .iloc[0]
    )

    with pytest.raises(ValueError):
        repository.get_product_risk_drivers(
            product_id=int(product_region["product_id"]),
            region_id=int(product_region["region_id"]),
            n=n,
        )
        
def test_three_month_revenue_declines_use_consecutive_months(
    repository: RiskRepository,
) -> None:
    """Revenue comparisons should use consecutive calendar months."""

    result = repository.get_current_three_month_revenue_declines(
        n=100
    )

    expected_1m_ago = (
        result["current_observation_month"]
        - pd.offsets.MonthBegin(1)
    )

    expected_2m_ago = (
        result["current_observation_month"]
        - pd.offsets.MonthBegin(2)
    )

    expected_3m_ago = (
        result["current_observation_month"]
        - pd.offsets.MonthBegin(3)
    )

    pd.testing.assert_series_equal(
        result["observation_month_1m_ago"].reset_index(drop=True),
        expected_1m_ago.reset_index(drop=True),
        check_names=False,
    )

    pd.testing.assert_series_equal(
        result["observation_month_2m_ago"].reset_index(drop=True),
        expected_2m_ago.reset_index(drop=True),
        check_names=False,
    )

    pd.testing.assert_series_equal(
        result["observation_month_3m_ago"].reset_index(drop=True),
        expected_3m_ago.reset_index(drop=True),
        check_names=False,
    )


def test_three_month_revenue_declines_have_correct_change(
    repository: RiskRepository,
) -> None:
    """Total revenue change should match current minus three months ago."""

    result = repository.get_current_three_month_revenue_declines(
        n=100
    )

    expected_change = (
        result["current_revenue"]
        - result["revenue_3m_ago"]
    )

    assert np.allclose(
        result["total_revenue_change"],
        expected_change,
    )

    assert result["high_risk_probability"].is_monotonic_decreasing
    assert result["target_month"].nunique() == 1

def test_current_risk_transitions_reject_identical_levels(
    repository: RiskRepository,
) -> None:
    """A transition must contain two different risk levels."""

    with pytest.raises(
        ValueError,
        match="must be different",
    ):
        repository.get_current_risk_transitions(
            from_level="high",
            to_level="High Risk",
            n=10,
        )

def test_high_risk_revenue_exposure(
    repository: RiskRepository,
) -> None:
    """Exposure query should rank current High-Risk rows by revenue."""

    result = repository.get_high_risk_revenue_exposure(n=10)

    assert len(result) == 10
    assert result["exposure_rank"].tolist() == list(range(1, 11))
    assert result["predicted_risk_label"].eq("High Risk").all()
    assert result["revenue"].is_monotonic_decreasing
    assert result["target_month"].nunique() == 1

    expected_proxy = (
        result["revenue"]
        * result["high_risk_probability"]
    )

    assert np.allclose(
        result["risk_weighted_revenue_proxy"],
        expected_proxy,
    )
    
def test_top_risks_returns_requested_number(
    repository: RiskRepository,
) -> None:
    """The query should return exactly the requested number of rows."""

    result = repository.get_top_risk_product_regions(n=10)

    assert len(result) == 10
    assert result["risk_rank"].tolist() == list(range(1, 11))


def test_top_risks_uses_current_snapshot(
    repository: RiskRepository,
) -> None:
    """All returned rows should belong to one current target month."""

    result = repository.get_top_risk_product_regions(n=10)

    assert result["target_month"].nunique() == 1
    assert result["year_month"].nunique() == 1


def test_top_risks_has_deterministic_order(
    repository: RiskRepository,
) -> None:
    """Risk results should follow the documented sorting rules."""

    result = repository.get_top_risk_product_regions(n=100)

    expected = (
        result
        .sort_values(
            by=[
                "high_risk_probability",
                "risk_score_0_10",
                "product_id",
                "region_id",
            ],
            ascending=[False, False, True, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        result.reset_index(drop=True),
        expected,
    )


@pytest.mark.parametrize(
    "invalid_n",
    [True, 1.5, "10"],
)
def test_top_risks_rejects_non_integer_n(
    repository: RiskRepository,
    invalid_n: object,
) -> None:
    """Non-integer limits should be rejected."""

    with pytest.raises(TypeError):
        repository.get_top_risk_product_regions(invalid_n)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid_n",
    [0, -1, 101],
)
def test_top_risks_rejects_out_of_range_n(
    repository: RiskRepository,
    invalid_n: int,
) -> None:
    """Limits outside 1–100 should be rejected."""

    with pytest.raises(ValueError):
        repository.get_top_risk_product_regions(invalid_n)


def get_existing_product_region(
    repository: RiskRepository,
) -> tuple[int, int]:
    """Return an existing product-region pair for history tests."""

    current_row = (
        repository
        .get_top_risk_product_regions(n=1)
        .iloc[0]
    )

    return (
        int(current_row["product_id"]),
        int(current_row["region_id"]),
    )


def test_product_history_returns_requested_months(
    repository: RiskRepository,
) -> None:
    """History should return the requested number of months."""

    product_id, region_id = get_existing_product_region(repository)

    result = repository.get_product_risk_history(
        product_id=product_id,
        region_id=region_id,
        months=6,
    )

    assert len(result) == 6
    assert result["product_id"].eq(product_id).all()
    assert result["region_id"].eq(region_id).all()


def test_product_history_is_chronological(
    repository: RiskRepository,
) -> None:
    """History should be ordered from oldest to newest."""

    product_id, region_id = get_existing_product_region(repository)

    result = repository.get_product_risk_history(
        product_id=product_id,
        region_id=region_id,
        months=6,
    )

    assert result["target_month"].is_monotonic_increasing
    assert result["year_month"].is_monotonic_increasing


def test_product_history_includes_current_scoring_row(
    repository: RiskRepository,
) -> None:
    """The most recent history row should be the current prediction."""

    product_id, region_id = get_existing_product_region(repository)

    result = repository.get_product_risk_history(
        product_id=product_id,
        region_id=region_id,
        months=6,
    )

    latest_row = result.iloc[-1]

    assert latest_row["split"] == "scoring"
    assert pd.isna(latest_row["actual_risk_label"])


def test_product_history_raises_for_missing_data(
    repository: RiskRepository,
) -> None:
    """Unknown product-region combinations should raise an error."""

    with pytest.raises(
        RiskDataNotFoundError,
        match="No risk data found",
    ):
        repository.get_product_risk_history(
            product_id=999_999_999,
            region_id=999_999_999,
            months=6,
        )


@pytest.mark.parametrize(
    ("invalid_product_id", "expected_exception"),
    [
        (True, TypeError),
        (1.5, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_product_history_rejects_invalid_product_id(
    repository: RiskRepository,
    invalid_product_id: object,
    expected_exception: type[Exception],
) -> None:
    """Invalid product identifiers should be rejected."""

    _, region_id = get_existing_product_region(repository)

    with pytest.raises(expected_exception):
        repository.get_product_risk_history(
            product_id=invalid_product_id,  # type: ignore[arg-type]
            region_id=region_id,
            months=6,
        )


@pytest.mark.parametrize(
    ("invalid_months", "expected_exception"),
    [
        (True, TypeError),
        (1.5, TypeError),
        (0, ValueError),
        (61, ValueError),
    ],
)
def test_product_history_rejects_invalid_months(
    repository: RiskRepository,
    invalid_months: object,
    expected_exception: type[Exception],
) -> None:
    """Invalid month limits should be rejected."""

    product_id, region_id = get_existing_product_region(repository)

    with pytest.raises(expected_exception):
        repository.get_product_risk_history(
            product_id=product_id,
            region_id=region_id,
            months=invalid_months,  # type: ignore[arg-type]
        )

@pytest.mark.parametrize(
    ("input_level", "expected_label"),
    [
        ("low", "Low Risk"),
        ("medium risk", "Medium Risk"),
        (" HIGH ", "High Risk"),
    ],
)
def test_current_risks_by_level_filters_and_normalizes(
    repository: RiskRepository,
    input_level: str,
    expected_label: str,
) -> None:
    """Risk-level queries should normalize and filter labels."""

    result = repository.get_current_risks_by_level(
        level=input_level,
        n=5,
    )

    assert len(result) == 5
    assert result["predicted_risk_label"].eq(expected_label).all()
    assert result["high_risk_probability"].is_monotonic_decreasing
    assert result["target_month"].nunique() == 1


@pytest.mark.parametrize(
    ("invalid_level", "expected_exception"),
    [
        (42, TypeError),
        ("", ValueError),
        ("Critical", ValueError),
    ],
)
def test_current_risks_by_level_rejects_invalid_values(
    repository: RiskRepository,
    invalid_level: object,
    expected_exception: type[Exception],
) -> None:
    """Unsupported risk levels should be rejected."""

    with pytest.raises(expected_exception):
        repository.get_current_risks_by_level(
            level=invalid_level,  # type: ignore[arg-type]
            n=5,
        )


def test_current_risks_above_probability_filters_rows(
    repository: RiskRepository,
) -> None:
    """Probability filters should return only qualifying rows."""

    result = repository.get_current_risks_above_probability(
        min_probability=0.7,
        n=100,
    )

    assert not result.empty
    assert result["high_risk_probability"].ge(0.7).all()
    assert result["high_risk_probability"].is_monotonic_decreasing
    assert result["target_month"].nunique() == 1


@pytest.mark.parametrize(
    ("invalid_probability", "expected_exception"),
    [
        (True, TypeError),
        ("0.7", TypeError),
        (-0.1, ValueError),
        (1.1, ValueError),
    ],
)
def test_probability_filter_rejects_invalid_values(
    repository: RiskRepository,
    invalid_probability: object,
    expected_exception: type[Exception],
) -> None:
    """Invalid probability thresholds should be rejected."""

    with pytest.raises(expected_exception):
        repository.get_current_risks_above_probability(
            min_probability=invalid_probability,  # type: ignore[arg-type]
            n=5,
        )