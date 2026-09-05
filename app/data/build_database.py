# Ingestion implementation 

# Build the local DuckDB database from validated EWS prediction outputs

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.config import (DATABASE_PATH, PREDICTIONS_PATH, 
MODEL_CONTRIBUTIONS_CSV_PATH)

KEY_COLUMNS = [
    "product_id",
    "region_id",
    "year_month",
]

REQUIRED_COLUMNS = [
    "product_id",
    "product_name",
    "product_line",
    "product_category",
    "lifecycle_stage",
    "region_id",
    "region",
    "year_month",
    "target_month",
    "split",
    "model_scope",
    "actual_risk_label_num",
    "actual_risk_label",
    "predicted_risk_label_num",
    "predicted_risk_label",
    "prob_low_risk",
    "prob_medium_risk",
    "high_risk_probability",
    "risk_score",
    "risk_score_0_10",
    "selected_high_risk_threshold",
    "is_any_risk_alert",
    "is_high_risk_alert",
    "revenue",
    "revenue_at_risk_proxy",
    "business_risk_indicators",
    "recommended_action",
    "business_indicator_count",
    "monitoring_priority",
    "units_sold",
    "unique_customers",
    "estimated_gross_profit",
    "estimated_gross_margin_pct"
]

NULLABLE_INTEGER_COLUMNS = [
    "next_month_risk_label",
    "actual_risk_label_num",
    "is_false_alarm",
    "is_missed_high_risk",
]

# Model contribution data contract
MODEL_CONTRIBUTION_REQUIRED_COLUMNS = {
    "split",
    "split_row_number",
    "product_id",
    "region_id",
    "year_month",
    "driver_rank",
    "feature",
    "feature_label",
    "explained_class_num",
    "explained_class",
    "explained_class_probability",
    "contribution_to_explained_class_probability",
    "contribution_to_high_risk_probability",
    "contribution_percentage_points",
    "direction",
}

## Entity = current produkt-region prediction 
MODEL_CONTRIBUTION_ENTITY_KEY = [
    "product_id",
    "region_id",
    "year_month",
]

## Grain identifies the driver
MODEL_CONTRIBUTION_GRAIN_KEY = [
    "product_id",
    "region_id",
    "year_month",
    "driver_rank",
]

def load_and_validate_model_contributions(
    path: Path,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Load and validate local model contributions for scoring rows.

    Args:
        path: Path to the model-contribution CSV file.
        predictions: Validated prediction DataFrame used to verify
            that every current scoring entity has model contributions.

    Returns:
        A validated DataFrame containing five ranked model
        contributions per current product-region prediction.

    Raises:
        FileNotFoundError: If the contribution file does not exist.
        ValueError: If its schema, grain, ranks, calculations, or
            prediction coverage are invalid.
    """

    if not path.exists():
        raise FileNotFoundError(
            "Model-contribution CSV not found. "
            f"Expected path: {path.resolve()}"
        )

    contributions = pd.read_csv(path)

    missing_columns = (
        MODEL_CONTRIBUTION_REQUIRED_COLUMNS
        - set(contributions.columns)
    )

    if missing_columns:
        raise ValueError(
            "Model-contribution CSV is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    contributions["year_month"] = pd.to_datetime(
        contributions["year_month"],
        errors="raise",
    )

    key_columns_with_missing_values = [
        column
        for column in MODEL_CONTRIBUTION_GRAIN_KEY
        if contributions[column].isna().any()
    ]

    if key_columns_with_missing_values:
        raise ValueError(
            "Model-contribution grain contains missing values in: "
            f"{key_columns_with_missing_values}"
        )

    if not contributions["split"].eq("scoring").all():
        unexpected_splits = sorted(
            contributions.loc[
                ~contributions["split"].eq("scoring"),
                "split",
            ]
            .astype(str)
            .unique()
            .tolist()
        )
        raise ValueError(
            "Model contributions must contain only scoring rows. "
            f"Unexpected splits: {unexpected_splits}"
        )

    duplicate_count = contributions.duplicated(
        MODEL_CONTRIBUTION_GRAIN_KEY
    ).sum()

    if duplicate_count:
        raise ValueError(
            "Duplicate model-contribution grain keys found: "
            f"{duplicate_count}"
        )

    rank_summary = (
        contributions
        .groupby(
            MODEL_CONTRIBUTION_ENTITY_KEY,
            dropna=False,
        )["driver_rank"]
        .agg(
            contribution_count="count",
            distinct_rank_count="nunique",
            minimum_rank="min",
            maximum_rank="max",
        )
    )

    invalid_rank_groups = rank_summary.loc[
        (rank_summary["contribution_count"] != 5)
        | (rank_summary["distinct_rank_count"] != 5)
        | (rank_summary["minimum_rank"] != 1)
        | (rank_summary["maximum_rank"] != 5)
    ]

    if not invalid_rank_groups.empty:
        raise ValueError(
            "Every scoring product-region must have exactly "
            "the driver ranks 1 through 5. "
            f"Invalid combinations: {len(invalid_rank_groups)}"
        )

    scoring_predictions = predictions.loc[
        predictions["split"].eq("scoring")
    ].copy()

    if scoring_predictions.empty:
        raise ValueError(
            "Prediction data does not contain scoring rows."
        )

    scoring_predictions["year_month"] = pd.to_datetime(
        scoring_predictions["year_month"],
        errors="raise",
    )
    scoring_predictions["target_month"] = pd.to_datetime(
        scoring_predictions["target_month"],
        errors="raise",
    )

    latest_target_month = scoring_predictions[
        "target_month"
    ].max()

    current_scoring_predictions = scoring_predictions.loc[
        scoring_predictions["target_month"].eq(
            latest_target_month
        )
    ].copy()

    expected_entities = (
        current_scoring_predictions[
            MODEL_CONTRIBUTION_ENTITY_KEY
        ]
        .drop_duplicates()
    )

    actual_entities = (
        contributions[
            MODEL_CONTRIBUTION_ENTITY_KEY
        ]
        .drop_duplicates()
    )

    entity_coverage = expected_entities.merge(
        actual_entities,
        on=MODEL_CONTRIBUTION_ENTITY_KEY,
        how="outer",
        indicator=True,
    )

    missing_contribution_entities = (
        entity_coverage["_merge"].eq("left_only").sum()
    )
    orphan_contribution_entities = (
        entity_coverage["_merge"].eq("right_only").sum()
    )

    if (
        missing_contribution_entities
        or orphan_contribution_entities
    ):
        raise ValueError(
            "Model contributions do not match the current "
            "scoring population. "
            f"Missing entities: {missing_contribution_entities}; "
            f"orphan entities: {orphan_contribution_entities}."
        )

    class_check = contributions.merge(
        current_scoring_predictions[
            MODEL_CONTRIBUTION_ENTITY_KEY
            + ["predicted_risk_label"]
        ],
        on=MODEL_CONTRIBUTION_ENTITY_KEY,
        how="left",
        validate="many_to_one",
    )

    class_mismatch_count = (
        class_check["explained_class"]
        != class_check["predicted_risk_label"]
    ).sum()

    if class_mismatch_count:
        raise ValueError(
            "Explained classes do not match prediction labels. "
            f"Mismatching rows: {class_mismatch_count}"
        )

    expected_percentage_points = (
        contributions[
            "contribution_to_explained_class_probability"
        ]
        * 100
    )

    percentage_point_difference = (
        contributions["contribution_percentage_points"]
        - expected_percentage_points
    ).abs()

    maximum_percentage_point_difference = (
        percentage_point_difference.max()
    )

    if maximum_percentage_point_difference > 1e-8:
        raise ValueError(
            "contribution_percentage_points is inconsistent "
            "with the explained-class contribution. "
            "Maximum difference: "
            f"{maximum_percentage_point_difference}"
        )

    return contributions



# PREDICTIONS
class DataContractError(ValueError):
    """Raised when an EWS source violates the expected data contract."""


def load_predictions(path: Path = PREDICTIONS_PATH) -> pd.DataFrame:
    """Read, normalize, and validate the EWS prediction CSV."""

    if not path.exists():
        raise FileNotFoundError(
            f"Prediction file not found: {path.resolve()}"
        )

    predictions = pd.read_csv(
        path,
        sep=";",
        decimal=",",
        low_memory=False,
    )

    missing_columns = sorted(
        set(REQUIRED_COLUMNS) - set(predictions.columns)
    )

    if missing_columns:
        raise DataContractError(
            f"Required columns are missing: {missing_columns}"
        )

    predictions["year_month"] = pd.to_datetime(
        predictions["year_month"],
        errors="raise",
    )

    predictions["target_month"] = pd.to_datetime(
        predictions["target_month"],
        errors="raise",
    )

    for column in NULLABLE_INTEGER_COLUMNS:
        if column in predictions.columns:
            predictions[column] = (
                pd.to_numeric(predictions[column], errors="raise")
                .astype("Int64")
            )

    validate_predictions(predictions)

    return predictions


def validate_predictions(predictions: pd.DataFrame) -> None:
    """Validate keys, periods, probabilities, scores, and scoring labels."""

    duplicate_count = predictions.duplicated(
        subset=KEY_COLUMNS
    ).sum()

    if duplicate_count:
        raise DataContractError(
            f"Found {duplicate_count} duplicate prediction keys."
        )

    probability_columns = [
        "prob_low_risk",
        "prob_medium_risk",
        "high_risk_probability",
    ]

    probability_sum = predictions[probability_columns].sum(axis=1)

    if not np.allclose(
        probability_sum.to_numpy(),
        1.0,
        atol=1e-9,
    ):
        raise DataContractError(
            "Class probabilities do not sum to 1."
        )

    if not predictions["high_risk_probability"].between(0, 1).all():
        raise DataContractError(
            "High-risk probabilities must be between 0 and 1."
        )

    expected_risk_score = (
        predictions["high_risk_probability"] * 100
    ).round(1)

    if not np.allclose(
        predictions["risk_score"],
        expected_risk_score,
    ):
        raise DataContractError(
            "risk_score does not equal the rounded "
            "high-risk probability percentage."
        )

    expected_target_month = (
        predictions["year_month"]
        + pd.offsets.MonthBegin(1)
    )

    if not expected_target_month.equals(
        predictions["target_month"]
    ):
        raise DataContractError(
            "target_month is not one month after year_month."
        )

    scoring_rows = predictions.loc[
        predictions["split"].eq("scoring")
    ]

    if scoring_rows.empty:
        raise DataContractError(
            "No scoring rows were found."
        )

    if not scoring_rows["actual_risk_label_num"].isna().all():
        raise DataContractError(
            "Scoring rows must not contain actual risk labels."
        )

# DATABASE BUILDING
def build_database(
    predictions_path: Path = PREDICTIONS_PATH,
    database_path: Path = DATABASE_PATH,
) -> dict[str, object]:
    """Create the prediction table and current-risk view in DuckDB."""

    predictions = load_predictions(predictions_path)

    model_contributions = load_and_validate_model_contributions(
    MODEL_CONTRIBUTIONS_CSV_PATH,
    predictions)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True)

    connection = duckdb.connect(str(database_path))

    try:
        connection.execute("BEGIN")
        connection.register("_prediction_frame", predictions)
        connection.register(
            "model_contributions_dataframe",
            model_contributions)

        connection.execute(
            """
            CREATE OR REPLACE TABLE risk_predictions_raw AS
            SELECT *
            FROM _prediction_frame
            """)
        connection.execute(
            """
            CREATE OR REPLACE VIEW current_risk_snapshot AS
            SELECT
                product_id,
                product_name,
                product_line,
                product_category,
                lifecycle_stage,
                region_id,
                region,
                year_month,
                target_month,
                split,
                model_scope,
                predicted_risk_label_num,
                predicted_risk_label,
                prob_low_risk,
                prob_medium_risk,
                high_risk_probability,
                risk_score,
                risk_score_0_10,
                selected_high_risk_threshold,
                is_any_risk_alert,
                is_high_risk_alert,
                units_sold,
                revenue,
                unique_customers,
                estimated_gross_profit,
                estimated_gross_margin_pct,
                revenue_at_risk_proxy,
                business_risk_indicators,
                recommended_action,
                business_indicator_count,
                monitoring_priority
            FROM risk_predictions_raw
            WHERE split = 'scoring'
              AND target_month = (
                  SELECT MAX(target_month)
                  FROM risk_predictions_raw
                  WHERE split = 'scoring'
              )
            """
        )

        connection.execute(
    """
    CREATE OR REPLACE TABLE scoring_model_contributions AS
    SELECT
        CAST(split AS VARCHAR) AS split,
        CAST(split_row_number AS BIGINT)
            AS split_row_number,
        CAST(product_id AS BIGINT) AS product_id,
        CAST(region_id AS BIGINT) AS region_id,
        CAST(year_month AS DATE) AS year_month,
        CAST(driver_rank AS INTEGER) AS driver_rank,
        CAST(feature AS VARCHAR) AS feature,
        CAST(feature_label AS VARCHAR) AS feature_label,
        CAST(explained_class_num AS INTEGER)
            AS explained_class_num,
        CAST(explained_class AS VARCHAR)
            AS explained_class,
        CAST(explained_class_probability AS DOUBLE)
            AS explained_class_probability,
        CAST(
            contribution_to_explained_class_probability
            AS DOUBLE
        ) AS contribution_to_explained_class_probability,
        CAST(
            contribution_to_high_risk_probability
            AS DOUBLE
        ) AS contribution_to_high_risk_probability,
        CAST(contribution_percentage_points AS DOUBLE)
            AS contribution_percentage_points,
        CAST(direction AS VARCHAR) AS direction
    FROM model_contributions_dataframe
    """)

        raw_row_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM risk_predictions_raw
            """
        ).fetchone()[0]

        current_row_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM current_risk_snapshot
            """
        ).fetchone()[0]

        latest_target_month = connection.execute(
            """
            SELECT MAX(target_month)
            FROM current_risk_snapshot
            """
        ).fetchone()[0]

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    return {
        "database_path": database_path,
        "raw_row_count": raw_row_count,
        "current_row_count": current_row_count,
        "latest_target_month": latest_target_month}




def main() -> None:
    """Build the database and print a compact build summary."""

    summary = build_database()

    print(f"Database: {summary['database_path']}")
    print(f"Raw prediction rows: {summary['raw_row_count']}")
    print(f"Current snapshot rows: {summary['current_row_count']}")
    print(f"Latest target month: {summary['latest_target_month']}")
    print("Database build completed successfully.")


if __name__ == "__main__":
    main()