"""
Validación cruzada SEDE vs Stack Exchange API.

Objetivo: comprobar que conteos diarios de preguntas por tag obtenidos
manualmente desde Stack Exchange Data Explorer (SEDE) coinciden con los
de la API pública (api.stackexchange.com). Si coinciden, queda justificado
migrar a una fuente alternativa (Data Dump o BigQuery) sin riesgo de
sesgo de selección entre fuentes.

Uso:
    python -m src.data.validate_api_vs_sede --year 2023 --month 5 \
        --tags python javascript java pandas reactjs

Restricciones:
    - Solo endpoints públicos de api.stackexchange.com.
    - Sin claves privadas, sin pagos, sin evasión de anti-bot.
    - Respeta backoff sugerido por la API.
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


API_BASE = "https://api.stackexchange.com/2.3"
SITE = "stackoverflow"


def _utc_ts(d: datetime) -> int:
    return calendar.timegm(d.timetuple())


def create_total_filter(session: requests.Session, key: str | None = None) -> str:
    """Crea un filter custom que retorna .total, .has_more, .quota_remaining."""
    params = {
        "include": ".total;.has_more;.quota_remaining",
        "base": "none",
        "unsafe": "false",
    }
    if key:
        params["key"] = key
    r = session.get(f"{API_BASE}/filters/create", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "items" not in data or not data["items"]:
        raise RuntimeError(f"Respuesta inesperada de /filters/create: {data}")
    return data["items"][0]["filter"]


def fetch_daily_count(
    session: requests.Session,
    tag: str,
    day: datetime,
    filter_id: str,
    polite_sleep: float = 0.4,
) -> int:
    """Devuelve el total de preguntas etiquetadas con tag creadas el día UTC."""
    from_ts = _utc_ts(day)
    to_ts = _utc_ts(day + timedelta(days=1))
    r = session.get(
        f"{API_BASE}/questions",
        params={
            "fromdate": from_ts,
            "todate": to_ts,
            "tagged": tag,
            "site": SITE,
            "pagesize": 1,
            "filter": filter_id,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    backoff = data.get("backoff")
    if backoff:
        time.sleep(float(backoff) + 0.1)
    time.sleep(polite_sleep)
    if "total" not in data:
        raise RuntimeError(
            f"Respuesta sin 'total' para tag={tag} day={day:%Y-%m-%d}: {data}"
        )
    return int(data["total"])


def days_in_month(year: int, month: int) -> Iterable[datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    d = start
    while d < end:
        yield d
        d += timedelta(days=1)


def load_sede_baseline(
    raw_dir: Path, year: int, month: int, probe_tags: list[str]
) -> pd.DataFrame:
    pattern = f"stackoverflow_question_type_raw_{year:04d}-{month:02d}-*.csv"
    files = sorted(raw_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No hay raw para {year}-{month:02d} en {raw_dir}")
    frames = []
    for f in files:
        frames.append(pd.read_csv(f, usecols=["tag", "question_id", "creation_date"]))
    df = pd.concat(frames, ignore_index=True)
    df["tag"] = df["tag"].replace(
        {
            "selenium-webdriver": "selenium",
            "selenium-chromedriver": "selenium",
            "webdriver": "selenium",
            "chromedriver": "selenium",
        }
    )
    df = df.drop_duplicates(["question_id", "tag"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["creation_date"]).dt.date
    df = df[df["tag"].isin(probe_tags)]
    daily = (
        df.groupby(["tag", "date"]).size().reset_index(name="sede_count")
    )
    return daily


def run(year: int, month: int, probe_tags: list[str], out_dir: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    raw_dir = root / "data" / "raw" / "stackoverflow"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Cargando baseline SEDE para {year}-{month:02d}...")
    sede = load_sede_baseline(raw_dir, year, month, probe_tags)
    print(f"      Filas SEDE (tag,date): {len(sede)}")

    print("[2/3] Creando filter de API y descargando totales por día...")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "ai-knowledge-commons-shock/validation (academic research)",
            "Accept": "application/json",
        }
    )
    filter_id = create_total_filter(session)
    print(f"      Filter ID: {filter_id}")

    rows = []
    for tag in probe_tags:
        for day in days_in_month(year, month):
            try:
                total = fetch_daily_count(session, tag, day, filter_id)
                rows.append({"tag": tag, "date": day.date(), "api_count": total})
                print(f"      {tag} {day:%Y-%m-%d} api={total}")
            except Exception as exc:
                print(f"      ERROR {tag} {day:%Y-%m-%d}: {exc}", file=sys.stderr)
                rows.append({"tag": tag, "date": day.date(), "api_count": None})
    api_df = pd.DataFrame(rows)

    print("[3/3] Comparando SEDE vs API...")
    merged = api_df.merge(sede, on=["tag", "date"], how="outer").fillna(0)
    merged["delta"] = merged["api_count"].astype(float) - merged["sede_count"].astype(float)
    merged["rel_delta_pct"] = (
        merged["delta"] / merged["sede_count"].replace(0, pd.NA) * 100.0
    )

    out_csv = out_dir / f"_validation_api_vs_sede_{year}-{month:02d}.csv"
    merged.to_csv(out_csv, index=False)
    print(f"\nGuardado: {out_csv}")

    summary = (
        merged.assign(abs_delta=merged["delta"].abs())
        .groupby("tag")
        .agg(
            n_days=("date", "count"),
            sede_total=("sede_count", "sum"),
            api_total=("api_count", "sum"),
            max_abs_delta=("abs_delta", "max"),
            mean_abs_delta=("abs_delta", "mean"),
        )
        .reset_index()
    )
    summary["diff_pct"] = (
        (summary["api_total"] - summary["sede_total"]) / summary["sede_total"] * 100
    )
    print("\n=== Resumen por tag ===")
    print(summary.to_string(index=False))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument(
        "--tags",
        nargs="+",
        default=["python", "javascript", "java", "pandas", "reactjs"],
    )
    p.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    args = p.parse_args()
    run(args.year, args.month, args.tags, args.out_dir)


if __name__ == "__main__":
    main()
