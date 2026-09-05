"""Deterministic read-only queries for EWS risk data."""

from __future__ import annotations

from numbers import Real
from pathlib import Path

import duckdb
import pandas as pd

from app.config import DATABASE_PATH


class RiskDataNotFoundError(LookupError):
    """Raised when requested EWS risk data does not exist."""


RISK_LEVEL_ALIASES = {
    "low": "Low Risk",
    "low risk": "Low Risk",
    "medium": "Medium Risk",
    "medium risk": "Medium Risk",
    "high": "High Risk",
    "high risk": "High Risk",
}


def validate_limit(n: int) -> int:
    """Validate and return an Assistant query row limit."""

    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an integer.")

    if not 1 <= n <= 100:
        raise ValueError("n must be between 1 and 100.")

    return n

# Validate the number of requested local model drivers
def validate_driver_limit(n: int) -> int:
    n = validate_limit(n)

    if n > 5:
        raise ValueError(
            "n must be between 1 and 5 for model drivers."
        )

    return n


def normalize_risk_level(level: str) -> str:
    """Convert a supported risk-level alias to its canonical label."""

    if not isinstance(level, str):
        raise TypeError("level must be a string.")

    normalized_level = level.strip().casefold()

    if normalized_level not in RISK_LEVEL_ALIASES:
        allowed_levels = ", ".join(
            sorted(set(RISK_LEVEL_ALIASES.values()))
        )
        raise ValueError(
            f"Unknown risk level: {level!r}. "
            f"Allowed levels: {allowed_levels}."
        )

    return RISK_LEVEL_ALIASES[normalized_level]


def validate_probability(value: Real) -> float:
    """Validate and return a probability on the 0–1 scale."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(
            "min_probability must be a numeric value."
        )

    probability = float(value)

    if not 0 <= probability <= 1:
        raise ValueError(
            "min_probability must be between 0 and 1."
        )

    return probability


class RiskRepository:
    """Provide controlled read-only access to EWS risk data."""

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        """Initialize the repository with a DuckDB database path."""

        self.database_path = Path(database_path)

        if not self.database_path.exists():
            raise FileNotFoundError(
                "DuckDB database not found. "
                "Run `python -m app.data.build_database` first. "
                f"Expected path: {self.database_path.resolve()}"
            )

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """Open a new read-only DuckDB connection."""

        return duckdb.connect(
            str(self.database_path),
            read_only=True,
        )

    def get_product_risk_drivers(
        self,
        product_id: int,
        region_id: int,
        n: int = 5,
    ) -> pd.DataFrame:
        """Return current local model drivers for one product-region.

        The result includes both the business-facing risk indicators
        and the technical local model contributions.

        A model contribution describes how a feature participated in
        the model's prediction. It is not evidence of business
        causality.

        Args:
            product_id: Positive product identifier.
            region_id: Positive region identifier.
            n: Number of ranked model drivers to return, from 1 to 5.

        Returns:
            A DataFrame ordered by ascending driver rank.

        Raises:
            TypeError: If an argument has the wrong type.
            ValueError: If an argument is outside its permitted range.
            RiskDataNotFoundError: If no current model contributions
                exist for the requested product-region.
        """

        for parameter_name, parameter_value in [
            ("product_id", product_id),
            ("region_id", region_id),
        ]:
            if (
                isinstance(parameter_value, bool)
                or not isinstance(parameter_value, int)
            ):
                raise TypeError(
                    f"{parameter_name} must be an integer."
                )

            if parameter_value <= 0:
                raise ValueError(
                    f"{parameter_name} must be positive."
                )

        n = validate_driver_limit(n)

        query = """
            SELECT
                risk.product_id,
                risk.product_name,
                risk.product_line,
                risk.product_category,
                risk.region_id,
                risk.region,
                risk.year_month,
                risk.target_month,

                risk.predicted_risk_label,
                risk.high_risk_probability,
                risk.risk_score,
                risk.risk_score_0_10,

                risk.business_risk_indicators,
                risk.recommended_action,

                contribution.driver_rank,
                contribution.feature,
                contribution.feature_label,

                contribution.explained_class,
                contribution.explained_class_probability,

                contribution
                    .contribution_to_explained_class_probability,

                contribution.contribution_percentage_points
                    AS explained_class_contribution_percentage_points,

                contribution.direction
                    AS explained_class_direction,

                contribution
                    .contribution_to_high_risk_probability,

                ROUND(
                    contribution
                        .contribution_to_high_risk_probability
                    * 100,
                    6
                ) AS high_risk_contribution_percentage_points

            FROM current_risk_snapshot AS risk

            INNER JOIN scoring_model_contributions
                AS contribution
                ON risk.product_id = contribution.product_id
                AND risk.region_id = contribution.region_id
                AND risk.year_month = contribution.year_month

            WHERE risk.product_id = ?
              AND risk.region_id = ?

            ORDER BY contribution.driver_rank ASC

            LIMIT ?
        """

        result = self._fetch_dataframe(
            query,
            [product_id, region_id, n],
        )

        if result.empty:
            raise RiskDataNotFoundError(
                "No current model contributions found for "
                f"product_id={product_id}, "
                f"region_id={region_id}."
            )

        return result
    
    def _fetch_dataframe(
        self,
        query: str,
        parameters: list[object] | None = None,
    ) -> pd.DataFrame:
        """Execute a read-only query and return its DataFrame result."""

        connection = self._connect()

        try:
            return connection.execute(
                query,
                parameters or [],
            ).fetchdf()

        finally:
            connection.close()

    def get_current_three_month_revenue_declines(
        self,
        n: int = 100,
    ) -> pd.DataFrame:
        """Return current product-regions with three consecutive declines.

        Three consecutive month-over-month declines require four
        consecutive monthly revenue observations.

        Args:
            n: Maximum number of product-region combinations to return.

        Returns:
            Matching current rows ordered by risk and revenue decline.
        """

        n = validate_limit(n)

        query = """
            WITH revenue_history AS (
                SELECT
                    product_id,
                    product_name,
                    product_line,
                    product_category,
                    region_id,
                    region,
                    year_month AS current_observation_month,
                    target_month,
                    split,
                    predicted_risk_label,
                    high_risk_probability,
                    risk_score,
                    revenue AS current_revenue,
                    LAG(year_month, 1) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY year_month
                    ) AS observation_month_1m_ago,
                    LAG(year_month, 2) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY year_month
                    ) AS observation_month_2m_ago,
                    LAG(year_month, 3) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY year_month
                    ) AS observation_month_3m_ago,
                    LAG(revenue, 1) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY year_month
                    ) AS revenue_1m_ago,
                    LAG(revenue, 2) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY year_month
                    ) AS revenue_2m_ago,
                    LAG(revenue, 3) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY year_month
                    ) AS revenue_3m_ago,
                    business_risk_indicators,
                    recommended_action
                FROM risk_predictions_raw
            ),
            latest_scoring_month AS (
                SELECT MAX(target_month) AS target_month
                FROM risk_predictions_raw
                WHERE split = 'scoring'
            ),
            matching_declines AS (
                SELECT
                    product_id,
                    product_name,
                    product_line,
                    product_category,
                    region_id,
                    region,
                    observation_month_3m_ago,
                    observation_month_2m_ago,
                    observation_month_1m_ago,
                    current_observation_month,
                    target_month,
                    revenue_3m_ago,
                    revenue_2m_ago,
                    revenue_1m_ago,
                    current_revenue,
                    current_revenue - revenue_3m_ago
                        AS total_revenue_change,
                    CASE
                        WHEN revenue_3m_ago IS NULL
                          OR revenue_3m_ago = 0
                        THEN NULL
                        ELSE
                            100.0
                            * (current_revenue - revenue_3m_ago)
                            / revenue_3m_ago
                    END AS total_revenue_change_pct,
                    predicted_risk_label,
                    high_risk_probability,
                    risk_score,
                    business_risk_indicators,
                    recommended_action
                FROM revenue_history
                WHERE split = 'scoring'
                  AND target_month = (
                      SELECT target_month
                      FROM latest_scoring_month
                  )
                  AND DATE_DIFF(
                      'month',
                      observation_month_1m_ago,
                      current_observation_month
                  ) = 1
                  AND DATE_DIFF(
                      'month',
                      observation_month_2m_ago,
                      current_observation_month
                  ) = 2
                  AND DATE_DIFF(
                      'month',
                      observation_month_3m_ago,
                      current_observation_month
                  ) = 3
                  AND current_revenue < revenue_1m_ago
                  AND revenue_1m_ago < revenue_2m_ago
                  AND revenue_2m_ago < revenue_3m_ago
            )
            SELECT *
            FROM matching_declines
            ORDER BY
                high_risk_probability DESC,
                total_revenue_change_pct ASC NULLS LAST,
                product_id ASC,
                region_id ASC
            LIMIT ?
        """

        return self._fetch_dataframe(
            query,
            [n]
        )
    
    def get_top_risk_product_regions(
        self,
        n: int = 10,
    ) -> pd.DataFrame:
        """Return the highest-risk current product-region predictions.

        Args:
            n: Number of product-region combinations to return.
                Must be between 1 and 100.

        Returns:
            A DataFrame ordered by descending high-risk probability.

        Raises:
            TypeError: If n is not an integer.
            ValueError: If n is outside the permitted range.
        """

        n = validate_limit(n)

        query = """
            WITH ranked_risks AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY
                            high_risk_probability DESC,
                            risk_score_0_10 DESC,
                            product_id ASC,
                            region_id ASC
                    ) AS risk_rank,
                    product_id,
                    product_name,
                    product_line,
                    product_category,
                    region_id,
                    region,
                    year_month,
                    target_month,
                    predicted_risk_label,
                    high_risk_probability,
                    risk_score,
                    risk_score_0_10,
                    revenue,
                    revenue_at_risk_proxy,
                    business_risk_indicators,
                    recommended_action
                FROM current_risk_snapshot
            )
            SELECT *
            FROM ranked_risks
            ORDER BY risk_rank
            LIMIT ?
        """

        return self._fetch_dataframe(
            query,
            [n],
        )

    def get_current_risk_transitions(
        self,
        from_level: str,
        to_level: str,
        n: int = 100,
    ) -> pd.DataFrame:
        """Return current product-region risk-level transitions.

        Args:
            from_level: Previous predicted risk level.
            to_level: Current predicted risk level.
            n: Maximum number of transitions to return.

        Returns:
            Matching transitions ordered by probability increase.

        Raises:
            TypeError: If a parameter has the wrong type.
            ValueError: If levels are invalid or identical.
        """

        canonical_from_level = normalize_risk_level(from_level)
        canonical_to_level = normalize_risk_level(to_level)
        n = validate_limit(n)

        if canonical_from_level == canonical_to_level:
            raise ValueError(
                "from_level and to_level must be different."
            )

        query = """
            WITH history_with_previous AS (
                SELECT
                    product_id,
                    product_name,
                    product_line,
                    product_category,
                    region_id,
                    region,
                    target_month AS current_target_month,
                    predicted_risk_label
                        AS current_predicted_risk_label,
                    high_risk_probability
                        AS current_high_risk_probability,
                    revenue AS current_revenue,
                    split,
                    LAG(target_month) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY target_month
                    ) AS previous_target_month,
                    LAG(predicted_risk_label) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY target_month
                    ) AS previous_predicted_risk_label,
                    LAG(high_risk_probability) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY target_month
                    ) AS previous_high_risk_probability,
                    LAG(revenue) OVER (
                        PARTITION BY product_id, region_id
                        ORDER BY target_month
                    ) AS previous_revenue,
                    business_risk_indicators,
                    recommended_action
                FROM risk_predictions_raw
            ),
            latest_scoring_month AS (
                SELECT MAX(target_month) AS target_month
                FROM risk_predictions_raw
                WHERE split = 'scoring'
            ),
            matching_transitions AS (
                SELECT
                    product_id,
                    product_name,
                    product_line,
                    product_category,
                    region_id,
                    region,
                    previous_target_month,
                    current_target_month,
                    previous_predicted_risk_label,
                    current_predicted_risk_label,
                    previous_high_risk_probability,
                    current_high_risk_probability,
                    current_high_risk_probability
                        - previous_high_risk_probability
                        AS high_risk_probability_change,
                    previous_revenue,
                    current_revenue,
                    current_revenue - previous_revenue
                        AS revenue_change,
                    CASE
                        WHEN previous_revenue IS NULL
                          OR previous_revenue = 0
                        THEN NULL
                        ELSE
                            100.0
                            * (current_revenue - previous_revenue)
                            / previous_revenue
                    END AS revenue_change_pct,
                    business_risk_indicators,
                    recommended_action
                FROM history_with_previous
                WHERE split = 'scoring'
                  AND current_target_month = (
                      SELECT target_month
                      FROM latest_scoring_month
                  )
                  AND previous_predicted_risk_label = ?
                  AND current_predicted_risk_label = ?
                  AND DATE_DIFF(
                      'month',
                      previous_target_month,
                      current_target_month
                  ) = 1
            )
            SELECT *
            FROM matching_transitions
            ORDER BY
                high_risk_probability_change DESC,
                current_high_risk_probability DESC,
                product_id ASC,
                region_id ASC
            LIMIT ?
        """

        return self._fetch_dataframe(
            query,
            [
                canonical_from_level,
                canonical_to_level,
                n,
            ],
        )
    
    def get_current_risk_by_region(self) -> pd.DataFrame:
        """Return current risk counts, rates, and exposure by region."""

        query = """
            SELECT
                region_id,
                region,
                target_month,
                COUNT(DISTINCT product_id) AS evaluated_product_count,
                CAST(
                    SUM(
                        CASE
                            WHEN predicted_risk_label = 'High Risk'
                            THEN 1
                            ELSE 0
                        END
                    )
                    AS BIGINT
                ) AS high_risk_product_count,
                ROUND(
                    100.0
                    * SUM(
                        CASE
                            WHEN predicted_risk_label = 'High Risk'
                            THEN 1
                            ELSE 0
                        END
                    )
                    / COUNT(*),
                    2
                ) AS high_risk_rate_pct,
                AVG(
                    high_risk_probability
                ) AS average_high_risk_probability,
                MAX(
                    high_risk_probability
                ) AS maximum_high_risk_probability,
                SUM(
                    revenue
                ) AS total_current_revenue,
                SUM(
                    CASE
                        WHEN predicted_risk_label = 'High Risk'
                        THEN revenue
                        ELSE 0
                    END
                ) AS high_risk_revenue_exposure,
                SUM(
                    revenue * high_risk_probability
                ) AS risk_weighted_revenue_proxy
            FROM current_risk_snapshot
            GROUP BY
                region_id,
                region,
                target_month
            ORDER BY
                high_risk_product_count DESC,
                high_risk_revenue_exposure DESC,
                region_id ASC
        """

        return self._fetch_dataframe(query)

    def get_high_risk_revenue_exposure(
        self,
        n: int = 10,
    ) -> pd.DataFrame:
        """Return high-risk product-regions with the highest revenue."""

        n = validate_limit(n)

        query = """
            WITH ranked_exposure AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY
                            revenue DESC NULLS LAST,
                            high_risk_probability DESC,
                            product_id ASC,
                            region_id ASC
                    ) AS exposure_rank,
                    product_id,
                    product_name,
                    product_line,
                    product_category,
                    region_id,
                    region,
                    year_month,
                    target_month,
                    predicted_risk_label,
                    high_risk_probability,
                    risk_score,
                    risk_score_0_10,
                    revenue,
                    revenue * high_risk_probability
                        AS risk_weighted_revenue_proxy,
                    estimated_gross_profit,
                    estimated_gross_margin_pct,
                    business_risk_indicators,
                    recommended_action
                FROM current_risk_snapshot
                WHERE predicted_risk_label = 'High Risk'
            )
            SELECT *
            FROM ranked_exposure
            ORDER BY exposure_rank
            LIMIT ?
        """

        return self._fetch_dataframe(
            query,
            [n],
        )
    
    def get_product_risk_history(
        self,
        product_id: int,
        region_id: int,
        months: int = 6,
    ) -> pd.DataFrame:
        """Return recent risk history for one product-region combination.

        Args:
            product_id: Positive product identifier.
            region_id: Positive region identifier.
            months: Number of recent months to return, between 1 and 60.

        Returns:
            A DataFrame ordered chronologically from oldest to newest.

        Raises:
            TypeError: If an argument has the wrong type.
            ValueError: If an argument is outside its permitted range.
            RiskDataNotFoundError: If the product-region combination
                does not exist.
        """

        for parameter_name, parameter_value in [
            ("product_id", product_id),
            ("region_id", region_id),
        ]:
            if (
                isinstance(parameter_value, bool)
                or not isinstance(parameter_value, int)
            ):
                raise TypeError(
                    f"{parameter_name} must be an integer."
                )

            if parameter_value <= 0:
                raise ValueError(
                    f"{parameter_name} must be positive."
                )

        if isinstance(months, bool) or not isinstance(months, int):
            raise TypeError("months must be an integer.")

        if not 1 <= months <= 60:
            raise ValueError("months must be between 1 and 60.")

        query = """
            WITH recent_history AS (
                SELECT
                    product_id,
                    product_name,
                    product_line,
                    product_category,
                    region_id,
                    region,
                    year_month,
                    target_month,
                    split,
                    actual_risk_label,
                    predicted_risk_label,
                    prob_low_risk,
                    prob_medium_risk,
                    high_risk_probability,
                    risk_score,
                    risk_score_0_10,
                    units_sold,
                    revenue,
                    unique_customers,
                    customer_count_growth_pct,
                    estimated_gross_margin_pct,
                    risk_factor_under_trend,
                    risk_factor_volatility,
                    risk_factor_sales_drop,
                    risk_factor_customer_drop,
                    stockout_flag,
                    business_risk_indicators
                FROM risk_predictions_raw
                WHERE product_id = ?
                  AND region_id = ?
                ORDER BY
                    target_month DESC,
                    year_month DESC
                LIMIT ?
            )
            SELECT *
            FROM recent_history
            ORDER BY
                target_month ASC,
                year_month ASC
        """

        result = self._fetch_dataframe(
            query,
            [product_id, region_id, months],
        )

        if result.empty:
            raise RiskDataNotFoundError(
                "No risk data found for "
                f"product_id={product_id}, "
                f"region_id={region_id}."
            )

        return result

    def get_current_risks_by_level(
        self,
        level: str,
        n: int = 100,
    ) -> pd.DataFrame:
        """Return current product-region risks for one risk level."""

        canonical_level = normalize_risk_level(level)
        n = validate_limit(n)

        query = """
            SELECT
                product_id,
                product_name,
                product_line,
                product_category,
                region_id,
                region,
                year_month,
                target_month,
                predicted_risk_label,
                high_risk_probability,
                risk_score,
                risk_score_0_10,
                revenue,
                revenue_at_risk_proxy,
                business_risk_indicators,
                recommended_action
            FROM current_risk_snapshot
            WHERE predicted_risk_label = ?
            ORDER BY
                high_risk_probability DESC,
                risk_score_0_10 DESC,
                product_id ASC,
                region_id ASC
            LIMIT ?
        """

        return self._fetch_dataframe(
            query,
            [canonical_level, n],
        )

    def get_current_risks_above_probability(
        self,
        min_probability: float,
        n: int = 100,
    ) -> pd.DataFrame:
        """Return current risks at or above a probability threshold."""

        validated_probability = validate_probability(
            min_probability
        )
        n = validate_limit(n)

        query = """
            SELECT
                product_id,
                product_name,
                product_line,
                product_category,
                region_id,
                region,
                year_month,
                target_month,
                predicted_risk_label,
                high_risk_probability,
                risk_score,
                risk_score_0_10,
                revenue,
                revenue_at_risk_proxy,
                business_risk_indicators,
                recommended_action
            FROM current_risk_snapshot
            WHERE high_risk_probability >= ?
            ORDER BY
                high_risk_probability DESC,
                risk_score_0_10 DESC,
                product_id ASC,
                region_id ASC
            LIMIT ?
        """

        return self._fetch_dataframe(
            query,
            [validated_probability, n],
        )