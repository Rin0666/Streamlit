from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


DATA_SOURCES_DIR = Path(os.environ.get(
    "DASHBOARD_DATA_DIR", Path(__file__).resolve().parent.parent / "data_sources"
))


EXCEL_COLORS = {
    "blue": "#4F81BD",
    "red": "#C0504D",
    "green": "#9BBB59",
    "purple": "#8064A2",
    "teal": "#4BACC6",
    "orange": "#F79646",
    "deep_purple": "#76397B",
    "bright_purple": "#AB54B2",
    "cream": "#EEECE1",
}


@dataclass(frozen=True)
class ModelConfig:
    key: str
    label: str
    workbook_name: str
    available: bool = True

    @property
    def workbook_path(self) -> Path:
        return DATA_SOURCES_DIR / self.workbook_name


MODEL_CONFIGS = {
    "churn": ModelConfig(
        key="churn",
        label="Churn Prediction",
        workbook_name="churn_model_monitoring_data.xlsx",
    ),
    "visit": ModelConfig(
        key="visit",
        label="Visit Prediction",
        workbook_name="Visit Model Monitoring.xlsx",
        available=False,
    ),
}
