# Central configuration

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PREDICTIONS_PATH = (
    PROJECT_ROOT
    / "data"
    / "full_data"
    / "ml_interpretation_risk_output"
    / "risk_predictions_for_dashboard.csv"
)

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "assistant"
    / "ews.duckdb"
)


ML_OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "full_data"
    / "ml_interpretation_risk_output"
)

MODEL_CONTRIBUTIONS_CSV_PATH = (
    ML_OUTPUT_DIRECTORY
    / "scoring_local_path_contributions.csv"
)
