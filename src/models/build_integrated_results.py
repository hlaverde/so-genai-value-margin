import argparse
from pathlib import Path

import pandas as pd

from src.paths import DOCS_DIR, OUTPUTS_DIR, TABLES_DIR, ensure_directories
from src.utils.io import read_csv, write_csv
from src.utils.logging_utils import get_logger


PAPER_TABLES_DIR = OUTPUTS_DIR.parent / "paper" / "tables"


OUTCOME_LABELS = {
    "log_questions": "SO: log(1 + questions)",
    "log_answers": "SO: log(1 + answers)",
    "answer_rate": "SO: answer rate",
    "code_share": "SO: code share",
    "short_code_share": "SO: short-code share",
    "log_posts": "SO users: log(1 + posts)",
    "log_unique_users": "SO users: log(1 + unique users)",
    "log1p_events": "GitHub: log(1 + entry events)",
    "log1p_active_actors": "GitHub: log(1 + active actors)",
    "log1p_first_seen_actors_language": "GitHub: log(1 + first-seen actors)",
    "log1p_pr_events": "GitHub: log(1 + PR events)",
    "log1p_pr_first_seen_actors": "GitHub: log(1 + first-seen PR actors)",
    "log1p_issue_events": "GitHub: log(1 + issue/comment events)",
    "log1p_issue_first_seen_actors": "GitHub: log(1 + first-seen issue actors)",
}


def stars(p_value: float) -> str:
    if pd.isna(p_value):
        return ""
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.1:
        return "*"
    return ""


def fmt(value: float, digits: int = 3) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}"


def add_common_columns(df: pd.DataFrame) -> pd.DataFrame:
    df["stars"] = df["p_value"].map(stars)
    df["estimate_with_stars"] = df.apply(lambda row: f"{fmt(row['estimate'])}{row['stars']}", axis=1)
    df["std_error_fmt"] = df["std_error"].map(lambda value: f"({fmt(value)})")
    df["p_value_fmt"] = df["p_value"].map(lambda value: fmt(value))
    return df


def stackoverflow_core(did_path: Path) -> pd.DataFrame:
    did = read_csv(did_path)
    keep = ["log_questions", "log_answers", "answer_rate", "code_share", "short_code_share"]
    out = did[did["outcome"].isin(keep)].copy()
    out["evidence_block"] = "Stack Overflow core"
    out["specification"] = "Tag FE + week FE; SE clustered by tag"
    out["hypothesis"] = out["outcome"].map(
        {
            "log_questions": "H1",
            "log_answers": "H1",
            "answer_rate": "H1/H3",
            "code_share": "H3",
            "short_code_share": "H2/H3",
        }
    )
    out["outcome_label"] = out["outcome"].map(OUTCOME_LABELS)
    out["coefficient_name"] = "AI answerability x Post ChatGPT"
    out = out.rename(columns={"estimate": "estimate", "std_error": "std_error"})
    return out[
        [
            "evidence_block",
            "hypothesis",
            "outcome",
            "outcome_label",
            "coefficient_name",
            "estimate",
            "std_error",
            "p_value",
            "specification",
        ]
    ]


def stackoverflow_trend_robust(grid_path: Path) -> pd.DataFrame:
    grid = read_csv(grid_path)
    out = grid[
        grid["model"].eq("tag_fe_week_fe_tag_linear_trends")
        & grid["sample"].eq("baseline")
        & grid["ai_index"].eq("ai_answerability_zscore")
        & grid["outcome"].isin(["log_questions", "log_answers"])
    ].copy()
    out["evidence_block"] = "Stack Overflow trend-robust"
    out["hypothesis"] = "H1"
    out["outcome_label"] = out["outcome"].map(OUTCOME_LABELS)
    out["coefficient_name"] = "AI answerability x Post ChatGPT"
    out["specification"] = "Tag FE + week FE + tag-specific linear trends"
    return out[
        [
            "evidence_block",
            "hypothesis",
            "outcome",
            "outcome_label",
            "coefficient_name",
            "estimate",
            "std_error",
            "p_value",
            "specification",
        ]
    ]


def stackoverflow_user_heterogeneity(user_path: Path) -> pd.DataFrame:
    user = read_csv(user_path)
    keep_terms = ["ai_x_post", "ai_x_post_x_new"]
    out = user[user["outcome"].isin(["log_questions", "log_unique_users"]) & user["term"].isin(keep_terms)].copy()
    out["evidence_block"] = "Stack Overflow user heterogeneity"
    out["hypothesis"] = out["term"].map({"ai_x_post": "H1/H2", "ai_x_post_x_new": "H2"})
    out["outcome_label"] = out["outcome"].map(OUTCOME_LABELS)
    out["coefficient_name"] = out["term"].map(
        {
            "ai_x_post": "AI answerability x Post ChatGPT",
            "ai_x_post_x_new": "AI answerability x Post ChatGPT x new user",
        }
    )
    out["specification"] = "Tag-user-group FE + week FE"
    return out[
        [
            "evidence_block",
            "hypothesis",
            "outcome",
            "outcome_label",
            "coefficient_name",
            "estimate",
            "std_error",
            "p_value",
            "specification",
        ]
    ]


def github_extension(github_path: Path) -> pd.DataFrame:
    gh = read_csv(github_path)
    keep = [
        "log1p_first_seen_actors_language",
        "log1p_pr_first_seen_actors",
        "log1p_issue_first_seen_actors",
    ]
    out = gh[gh["treatment"].eq("so_dependence_log") & gh["outcome"].isin(keep)].copy()
    out = out.rename(columns={"coefficient": "estimate", "std_error_cluster_language": "std_error"})
    out["evidence_block"] = "GitHub extension"
    out["hypothesis"] = "H4"
    out["outcome_label"] = out["outcome"].map(OUTCOME_LABELS)
    out["coefficient_name"] = "SO dependence x Post ChatGPT"
    out["specification"] = "Language FE + week FE; SE clustered by language; top-1000 entry-oriented repos"
    return out[
        [
            "evidence_block",
            "hypothesis",
            "outcome",
            "outcome_label",
            "coefficient_name",
            "estimate",
            "std_error",
            "p_value",
            "specification",
        ]
    ]


def build_integrated_table(args: argparse.Namespace) -> pd.DataFrame:
    parts = [
        stackoverflow_core(args.stackoverflow_did),
        stackoverflow_trend_robust(args.stackoverflow_grid),
        stackoverflow_user_heterogeneity(args.stackoverflow_users),
        github_extension(args.github_models),
    ]
    out = pd.concat(parts, ignore_index=True)
    out = add_common_columns(out)
    return out


def latex_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("#", "\\#")
    )


def write_latex_table(df: pd.DataFrame, path: Path) -> None:
    rows = []
    rows.append("\\begin{table}[!htbp]")
    rows.append("\\centering")
    rows.append("\\caption{Integrated first-pass results}")
    rows.append("\\label{tab:integrated_results}")
    rows.append("\\resizebox{\\textwidth}{!}{%")
    rows.append("\\begin{tabular}{llllr}")
    rows.append("\\toprule")
    rows.append("Block & Hyp. & Outcome & Coefficient & Estimate \\\\")
    rows.append("\\midrule")
    for _, row in df.iterrows():
        rows.append(
            " & ".join(
                [
                    latex_escape(row["evidence_block"]),
                    latex_escape(row["hypothesis"]),
                    latex_escape(row["outcome_label"]),
                    latex_escape(row["coefficient_name"]),
                    f"{row['estimate_with_stars']} {row['std_error_fmt']}",
                ]
            )
            + " \\\\"
        )
    rows.append("\\bottomrule")
    rows.append("\\end{tabular}")
    rows.append("}")
    rows.append("\\begin{minipage}{0.96\\linewidth}")
    rows.append("\\footnotesize")
    rows.append(
        "Notes: Stars denote p $<$ 0.10, p $<$ 0.05, and p $<$ 0.01. "
        "All tables are generated from reproducible scripts. "
        "GitHub estimates are exploratory because language-level inference has few clusters."
    )
    rows.append("\\end{minipage}")
    rows.append("\\end{table}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_markdown_summary(df: pd.DataFrame, path: Path) -> None:
    so_questions = df[
        df["evidence_block"].eq("Stack Overflow core") & df["outcome"].eq("log_questions")
    ].iloc[0]
    so_answers = df[df["evidence_block"].eq("Stack Overflow core") & df["outcome"].eq("log_answers")].iloc[0]
    trend_questions = df[
        df["evidence_block"].eq("Stack Overflow trend-robust") & df["outcome"].eq("log_questions")
    ].iloc[0]
    github_first = df[
        df["evidence_block"].eq("GitHub extension") & df["outcome"].eq("log1p_first_seen_actors_language")
    ].iloc[0]

    text = f"""# Integrated Results Summary

This file is generated by `src/models/build_integrated_results.py`.

## Main Takeaways

1. The strongest result remains the Stack Overflow activity decline in high-AI-answerability tags after ChatGPT.
   - `log(1 + questions)`: {fmt(so_questions['estimate'])}, p = {fmt(so_questions['p_value'])}.
   - `log(1 + answers)`: {fmt(so_answers['estimate'])}, p = {fmt(so_answers['p_value'])}.
2. The core Stack Overflow result remains negative when adding tag-specific linear trends.
   - `log(1 + questions)`: {fmt(trend_questions['estimate'])}, p = {fmt(trend_questions['p_value'])}.
3. User-group results are directionally consistent for new users, but not precise enough to claim a clean differential new-user effect yet.
4. The GitHub language extension is currently null/inconclusive.
   - `log(1 + first-seen actors)`: {fmt(github_first['estimate'])}, p = {fmt(github_first['p_value'])}.

## Paper Framing

The current empirical center of the paper should be Stack Overflow: public question and answer production falls more in tags where pre-ChatGPT features suggest higher substitutability by generative AI.

GitHub should be framed as a secondary extension. With the current entry-oriented top-1000 repository sample, there is no robust evidence that more Stack-Overflow-dependent languages saw lower post-ChatGPT GitHub entry. This is substantively useful: it suggests that the knowledge-commons shock is clearer in public Q&A production than in aggregate open-source entry at the current level of measurement.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build integrated first-pass result tables for the paper.")
    parser.add_argument("--stackoverflow-did", type=Path, default=TABLES_DIR / "stackoverflow_did_real.csv")
    parser.add_argument("--stackoverflow-grid", type=Path, default=TABLES_DIR / "stackoverflow_identification_grid_real.csv")
    parser.add_argument("--stackoverflow-users", type=Path, default=TABLES_DIR / "stackoverflow_user_group_heterogeneity_real.csv")
    parser.add_argument("--github-models", type=Path, default=TABLES_DIR / "github_entry_top1000_language_entry_models.csv")
    parser.add_argument("--output-csv", type=Path, default=TABLES_DIR / "integrated_first_pass_results.csv")
    parser.add_argument("--output-tex", type=Path, default=PAPER_TABLES_DIR / "integrated_first_pass_results.tex")
    parser.add_argument("--output-md", type=Path, default=DOCS_DIR / "integrated_results_summary.md")
    return parser.parse_args()


def main() -> None:
    ensure_directories()
    args = parse_args()
    logger = get_logger(__name__)
    table = build_integrated_table(args)
    write_csv(table, args.output_csv)
    write_latex_table(table, args.output_tex)
    write_markdown_summary(table, args.output_md)
    logger.info("Wrote integrated CSV to %s", args.output_csv)
    logger.info("Wrote LaTeX table to %s", args.output_tex)
    logger.info("Wrote Markdown summary to %s", args.output_md)
    logger.info("\n%s", table[["evidence_block", "hypothesis", "outcome_label", "estimate_with_stars", "std_error_fmt", "p_value_fmt"]].to_string(index=False))


if __name__ == "__main__":
    main()
