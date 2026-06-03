from pathlib import Path

import pandas as pd

from src.data.build_panels import build_stackoverflow_analysis_panel
from src.data.clean_stackoverflow import clean_stackoverflow
from src.features.build_ai_answerability import build_ai_answerability
from src.features.build_post_complexity import build_post_complexity
from src.features.build_user_status import build_user_status


def test_simulated_stackoverflow_pipeline(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    input_dir = project_root / "data" / "simulated"
    interim_dir = tmp_path / "interim"

    outputs = clean_stackoverflow(input_dir, interim_dir)
    tag_week = pd.read_csv(outputs["tag_week"])
    user_tag_week = pd.read_csv(outputs["user_tag_week"])
    post_complexity_clean = pd.read_csv(outputs["post_complexity"])

    post_complexity = build_post_complexity(post_complexity_clean)
    user_status = build_user_status(user_tag_week)
    answerability = build_ai_answerability(tag_week, post_complexity)
    panel = build_stackoverflow_analysis_panel(tag_week, answerability)

    assert {"python", "kubernetes"} == set(answerability["tag"])
    assert "ai_answerability_zscore" in answerability.columns
    assert "ai_answerability_pca" in answerability.columns
    assert "ai_answerability_quantile" in answerability.columns
    assert "ai_answerability_structural" in answerability.columns
    assert user_status["new_user"].sum() > 0
    assert post_complexity["short_code_question"].sum() > 0
    assert panel["ai_answerability_zscore"].notna().all()
    assert len(panel) == len(tag_week)
