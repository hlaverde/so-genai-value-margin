"""
Descarga preguntas de Stack Overflow vía Stack Exchange API v2.3.

Sustituye el proceso manual SEDE + reCAPTCHA por un script reproducible
contra el endpoint público /questions. La validación cruzada en
mayo 2023 (ver src/data/validate_api_vs_sede.py) muestra match > 99.99%
entre ambas fuentes, lo que justifica esta migración.

Schema de salida (idéntico al de SEDE):
    tag, week_start, question_id, owner_user_id, creation_date, title,
    body_length, has_code, score, answer_count, has_accepted_answer, is_closed

Uso:
    # Sin clave (300 req/día por IP, solo apto para pruebas pequeñas):
    python -m src.data.fetch_stackoverflow_via_api \
        --start 2023-06-01 --end 2023-06-05

    # Con clave gratuita registrada en https://stackapps.com/apps/oauth/register
    # (10,000 req/día):
    set STACK_EXCHANGE_KEY=tu_clave_aqui
    python -m src.data.fetch_stackoverflow_via_api \
        --start 2023-06-01 --end 2023-07-01 --days 4

Restricciones cumplidas:
    - Solo endpoints públicos de api.stackexchange.com.
    - Respeta backoff sugerido por la API.
    - No automatiza SEDE ni evade anti-bot.
    - Reproducible 100% con Python.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests


API_BASE = "https://api.stackexchange.com/2.3"
SITE = "stackoverflow"


# Top 100 tags canonical (sin alias de selenium)
TOP_100_TAGS: set[str] = {
    ".net", ".net-core", "ajax", "algorithm", "amazon-web-services",
    "android", "android-studio", "angular", "apache-spark", "arrays",
    "asp.net", "asp.net-core", "asp.net-mvc", "azure", "bash",
    "c", "c#", "c++", "css", "csv",
    "dart", "database", "dataframe", "dictionary", "django",
    "docker", "excel", "express", "firebase", "flask",
    "flutter", "for-loop", "function", "ggplot2", "git",
    "go", "google-apps-script", "google-cloud-firestore",
    "google-cloud-platform", "google-sheets", "html", "ios", "java",
    "javascript", "jquery", "json", "keras", "kotlin", "kubernetes",
    "laravel", "linux", "list", "loops", "machine-learning", "macos",
    "matplotlib", "mongodb", "multithreading", "mysql", "node.js",
    "numpy", "opencv", "oracle-database", "pandas", "php", "postgresql",
    "powershell", "python", "python-3.x", "r", "react-native", "reactjs",
    "regex", "rest", "ruby", "ruby-on-rails", "scala", "selenium",
    "shell", "spring", "spring-boot", "sql", "sql-server", "string",
    "swift", "swiftui", "tensorflow", "tkinter", "typescript",
    "unity-game-engine", "vba", "visual-studio", "visual-studio-code",
    "vue.js", "web-scraping", "windows", "wordpress", "wpf",
    "xcode", "xml",
}

SELENIUM_ALIASES: dict[str, str] = {
    "selenium-webdriver": "selenium",
    "selenium-chromedriver": "selenium",
    "webdriver": "selenium",
    "chromedriver": "selenium",
}

ACCEPTED_TAGS: set[str] = TOP_100_TAGS | set(SELENIUM_ALIASES.keys())

OUTPUT_COLUMNS = [
    "tag", "week_start", "question_id", "owner_user_id", "creation_date",
    "title", "body_length", "has_code", "score", "answer_count",
    "has_accepted_answer", "is_closed",
]


def to_canonical(tag: str) -> str:
    return SELENIUM_ALIASES.get(tag, tag)


def utc_ts(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def week_start_of(dt: datetime) -> str:
    """Replica DATEADD(WEEK, DATEDIFF(WEEK, 0, dt), 0) de SQL Server.

    SQL Server cuenta semanas desde 1900-01-01 (un lunes). Esa función
    devuelve el lunes 00:00:00 de la semana de dt. En Python equivale a
    restar dt.weekday() días.
    """
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d %H:%M:%S").split(" ")[0] + " 00:00:00"


# Filter pre-creado para incluir question.body + .total + .has_more +
# .quota_remaining + .backoff sobre el base "default". Stack Exchange
# devuelve siempre el mismo ID para los mismos parámetros, por lo que
# este valor es estable y reproducible. Se usa por defecto para no
# consumir cuota de IP creando filters nuevos en cada corrida.
DEFAULT_FILTER_ID = "!20aKG._8Oscv*6djt*X3)"


def create_filter(session: requests.Session, key: str | None = None) -> str:
    """Filter que extiende 'default' con body, total, has_more, backoff.

    Pasa `key` para que la llamada se cobre contra la cuota de la app
    (10,000/día) en lugar de la cuota de IP (300/día). Si la API responde
    con throttle violation aún así, se usa el filter pre-creado conocido.
    """
    params = {
        "include": "question.body;.total;.has_more;.quota_remaining;.backoff",
        "base": "default",
        "unsafe": "false",
    }
    if key:
        params["key"] = key
    try:
        r = session.get(f"{API_BASE}/filters/create", params=params, timeout=30)
        if r.status_code == 400:
            data = r.json()
            if data.get("error_name") == "throttle_violation":
                print(
                    f"  [warn] /filters/create throttled, usando filter cacheado "
                    f"({DEFAULT_FILTER_ID})",
                    file=sys.stderr,
                )
                return DEFAULT_FILTER_ID
        r.raise_for_status()
        data = r.json()
        if "items" not in data or not data["items"]:
            raise RuntimeError(f"Filter creation failed: {data}")
        return data["items"][0]["filter"]
    except requests.HTTPError:
        raise


def question_to_rows(q: dict) -> list[dict]:
    tags_raw = q.get("tags") or []
    canonical = set()
    for t in tags_raw:
        if t in ACCEPTED_TAGS:
            canonical.add(to_canonical(t))
    if not canonical:
        return []

    creation_ts = q.get("creation_date")
    if creation_ts is None:
        return []
    creation_dt = datetime.fromtimestamp(creation_ts, tz=timezone.utc)
    creation_str = creation_dt.strftime("%Y-%m-%d %H:%M:%S")
    week_str = week_start_of(creation_dt)

    body = q.get("body") or ""
    title = q.get("title") or ""
    owner = q.get("owner") or {}
    owner_uid = owner.get("user_id", "")

    common = {
        "week_start": week_str,
        "question_id": q.get("question_id"),
        "owner_user_id": owner_uid,
        "creation_date": creation_str,
        "title": title,
        "body_length": len(body),
        "has_code": 1 if "<code>" in body else 0,
        "score": int(q.get("score", 0)),
        "answer_count": int(q.get("answer_count", 0)),
        "has_accepted_answer": 1 if q.get("accepted_answer_id") else 0,
        "is_closed": 1 if q.get("closed_date") else 0,
    }
    return [{"tag": tag, **common} for tag in sorted(canonical)]


class PageLimitExceeded(Exception):
    """La API tiene un tope de páginas (25 sin clave, ~200 con clave)."""


def _fetch_paginated(
    session: requests.Session,
    start_dt: datetime,
    end_dt: datetime,
    filter_id: str,
    key: str | None,
    max_pages: int,
    polite_sleep: float,
    verbose: bool,
) -> tuple[list[dict], dict]:
    """Paginación lineal en una sub-ventana. Lanza PageLimitExceeded si has_more
    sigue True al alcanzar max_pages (señal de dividir la ventana)."""
    rows: list[dict] = []
    page = 1
    questions_seen = 0
    requests_made = 0
    last_quota = None
    fromdate = utc_ts(start_dt)
    todate = utc_ts(end_dt)

    while True:
        params = {
            "site": SITE,
            "fromdate": fromdate,
            "todate": todate,
            "page": page,
            "pagesize": 100,
            "order": "asc",
            "sort": "creation",
            "filter": filter_id,
        }
        if key:
            params["key"] = key
        r = session.get(f"{API_BASE}/questions", params=params, timeout=60)
        requests_made += 1
        # 400 puede significar (a) page-limit excedido, o (b) throttle violation.
        # Distinguimos por el body.
        if r.status_code == 400:
            try:
                err = r.json()
            except Exception:
                err = {}
            ename = err.get("error_name", "")
            if ename == "throttle_violation":
                # Espera reportada por la API si viene en error_message
                msg = err.get("error_message", "")
                wait_s = 60
                # Mensajes tipo "more requests available in X seconds"
                import re
                m = re.search(r"in (\d+) seconds", msg)
                if m:
                    wait_s = min(int(m.group(1)) + 5, 600)
                if verbose:
                    print(
                        f"  [throttle] esperando {wait_s}s antes de reintentar "
                        f"page={page}",
                        file=sys.stderr,
                    )
                time.sleep(wait_s)
                continue
            if page > 1:
                # Asumimos page-limit hit; señalamos para dividir
                raise PageLimitExceeded(
                    f"HTTP 400 en page={page} ventana {start_dt}-{end_dt}"
                )
            # Otro 400 sin clasificar
            raise RuntimeError(f"HTTP 400 en page=1: {err}")
        if r.status_code == 429:
            if verbose:
                print("  HTTP 429, durmiendo 30s...", file=sys.stderr)
            time.sleep(30)
            continue
        r.raise_for_status()
        data = r.json()
        if "error_id" in data:
            raise RuntimeError(f"API error: {data}")

        for q in data.get("items", []):
            questions_seen += 1
            rows.extend(question_to_rows(q))

        last_quota = data.get("quota_remaining")
        backoff = data.get("backoff")
        if verbose:
            print(
                f"    [{start_dt:%m-%d %H:%M}-{end_dt:%m-%d %H:%M}] "
                f"page={page} +{len(data.get('items', []))} "
                f"rows={len(rows)} quota={last_quota} backoff={backoff or 0}",
                file=sys.stderr,
            )
        if backoff:
            time.sleep(float(backoff) + 0.2)
        else:
            time.sleep(polite_sleep)

        if not data.get("has_more"):
            break
        page += 1
        if page > max_pages:
            raise PageLimitExceeded(
                f"max_pages={max_pages} alcanzado en {start_dt}-{end_dt} con has_more=True"
            )

    return rows, {
        "requests_made": requests_made,
        "questions_seen": questions_seen,
        "rows_emitted": len(rows),
        "quota_remaining": last_quota,
    }


def fetch_window(
    session: requests.Session,
    start_dt: datetime,
    end_dt: datetime,
    filter_id: str,
    key: str | None,
    polite_sleep: float = 0.25,
    verbose: bool = True,
    sub_window_hours: int = 4,
    min_sub_window_minutes: int = 5,
) -> tuple[list[dict], dict]:
    """Descarga [start_dt, end_dt) usando sub-ventanas adaptativas.

    Sin clave la API limita a 25 páginas (2500 items). Con clave a ~200
    (20000 items). Para no depender del límite, dividimos en sub-ventanas
    de `sub_window_hours` y, si alguna excede, recursivamente la partimos
    a la mitad hasta `min_sub_window_minutes`.
    """
    max_pages_no_key = 24
    max_pages_with_key = 199
    max_pages = max_pages_with_key if key else max_pages_no_key

    rows: list[dict] = []
    stats = {"requests_made": 0, "questions_seen": 0, "rows_emitted": 0, "quota_remaining": None}

    def _recurse(s: datetime, e: datetime) -> None:
        try:
            r, st = _fetch_paginated(
                session, s, e, filter_id, key, max_pages, polite_sleep, verbose
            )
            rows.extend(r)
            stats["requests_made"] += st["requests_made"]
            stats["questions_seen"] += st["questions_seen"]
            stats["rows_emitted"] += st["rows_emitted"]
            stats["quota_remaining"] = st["quota_remaining"]
        except PageLimitExceeded as exc:
            span = e - s
            if span <= timedelta(minutes=min_sub_window_minutes):
                raise RuntimeError(
                    f"Ventana mínima ({min_sub_window_minutes}min) excedida sin agotar paginación: {exc}"
                )
            mid = s + span / 2
            if verbose:
                print(
                    f"  [split] {s:%m-%d %H:%M}-{e:%m-%d %H:%M} -> "
                    f"{s:%H:%M}/{mid:%H:%M}/{e:%H:%M}",
                    file=sys.stderr,
                )
            _recurse(s, mid)
            _recurse(mid, e)

    # Sub-ventanas iniciales por `sub_window_hours`
    cur = start_dt
    while cur < end_dt:
        nxt = min(cur + timedelta(hours=sub_window_hours), end_dt)
        _recurse(cur, nxt)
        cur = nxt

    return rows, stats


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Replica ORDER BY p.CreationDate, p.Id, t.TagName del SQL SEDE.
    rows_sorted = sorted(rows, key=lambda r: (r["creation_date"], r["question_id"], r["tag"]))
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        w.writeheader()
        for row in rows_sorted:
            w.writerow(row)


def daterange_windows(start: datetime, end: datetime, days: int) -> Iterable[tuple[datetime, datetime]]:
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    p.add_argument("--end", required=True, help="YYYY-MM-DD exclusive")
    p.add_argument("--days", type=int, default=4, help="Ventana en días por archivo")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/raw/stackoverflow"),
        help="Carpeta destino (raw)",
    )
    p.add_argument("--polite-sleep", type=float, default=0.25)
    p.add_argument(
        "--key",
        default=os.environ.get("STACK_EXCHANGE_KEY"),
        help="Stack Exchange key (también via env STACK_EXCHANGE_KEY)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Sobreescribir CSV existente",
    )
    args = p.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "ai-knowledge-commons-shock/research (academic, contact: replication)",
            "Accept": "application/json",
        }
    )

    if not args.key:
        print(
            "[WARN] Sin STACK_EXCHANGE_KEY. Quota=300 requests/IP/día.\n"
            "       Para descargas grandes registra una app gratuita en\n"
            "       https://stackapps.com/apps/oauth/register y exporta\n"
            "       STACK_EXCHANGE_KEY antes de correr.",
            file=sys.stderr,
        )

    print("[1/2] Creando filter de API...", file=sys.stderr)
    filter_id = create_filter(session, key=args.key)
    print(f"       Filter ID: {filter_id}", file=sys.stderr)

    print("[2/2] Descargando ventanas...", file=sys.stderr)
    total_stats = {"requests": 0, "questions": 0, "rows": 0, "files": 0}
    for win_start, win_end in daterange_windows(start, end, args.days):
        name = (
            f"stackoverflow_question_type_raw_"
            f"{win_start:%Y-%m-%d}_{win_end:%Y-%m-%d}.csv"
        )
        out_path = args.out_dir / name
        if out_path.exists() and not args.force:
            print(f"  [skip] {out_path.name} ya existe (usa --force para sobreescribir)",
                  file=sys.stderr)
            continue
        print(f"  Ventana {win_start:%Y-%m-%d} -> {win_end:%Y-%m-%d}", file=sys.stderr)
        rows, stats = fetch_window(
            session, win_start, win_end, filter_id, args.key, args.polite_sleep
        )
        write_csv(rows, out_path)
        print(
            f"  -> {out_path.name}: rows={stats['rows_emitted']} "
            f"questions={stats['questions_seen']} "
            f"requests={stats['requests_made']} "
            f"quota_remaining={stats['quota_remaining']}",
            file=sys.stderr,
        )
        total_stats["requests"] += stats["requests_made"]
        total_stats["questions"] += stats["questions_seen"]
        total_stats["rows"] += stats["rows_emitted"]
        total_stats["files"] += 1

    print(f"\nDone. {json.dumps(total_stats)}", file=sys.stderr)


if __name__ == "__main__":
    main()
