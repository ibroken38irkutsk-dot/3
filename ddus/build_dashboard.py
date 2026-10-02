"""Одностраничник «Бюджет ДДУС» в Superset (через REST API).

Запуск:
    python build_dashboard.py --url http://superset:8088 --user admin --password *** \
        --db-name "DDUS" [--schema public] [--export dashboard.zip]

Таблица ddus_budget должна быть загружена (etl_ddus.py), подключение к БД — создано
в Superset. Повторный запуск пересоздаёт графики и дашборд.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kit"))
from superset_kit import Dashboard, Superset, neg, pos, ratio, s  # noqa: E402

ART = "NOT is_detail"  # без строк «в т.ч.», чтобы не было двойного счёта
NONZERO = "(sd_year <> 0 OR expected_year <> 0 OR sd_5m <> 0 OR fact_5m <> 0)"

SD, EXP = s("sd_year", ART), s("expected_year", ART)
SD5, F5 = s("sd_5m", ART), s("fact_5m", ART)
DEV, DEV5 = f"{EXP} - {SD}", f"{F5} - {SD5}"

METRICS = {
    "Сд_26":               (SD, ",.1f"),
    "Ожид_26":             (EXP, ",.1f"),
    "Откл. Ожид/Сд":       (DEV, "+,.1f"),
    "Откл. Ожид/Сд, %":    (ratio(DEV, SD), "+.1%"),
    "Выше Сд (год)":       (pos(DEV), "+,.1f"),
    "Ниже Сд (год)":       (neg(DEV), "+,.1f"),
    "5 мес Сд":            (SD5, ",.1f"),
    "5 мес Факт":          (F5, ",.1f"),
    "5 мес Откл.":         (DEV5, "+,.1f"),
    "Исполнение 5 мес, %": (ratio(F5, SD5), ".1%"),
    "Выше Сд (5 мес)":     (pos(DEV5), "+,.1f"),
    "Ниже Сд (5 мес)":     (neg(DEV5), "+,.1f"),
    "Июнь-Дек Сд":         (s("sd_jun_dec", ART), ",.1f"),
    "Июнь-Дек Прогноз":    (s("forecast_jun_dec", ART), ",.1f"),
}

LABELS = {
    "activity": "Деятельность",
    "article": "Статья оборотов",
    "parent_article": "Родительская статья",
    "is_detail": "Строка «в т.ч.»",
    "comment": "Пояснение",
}

HEADER = """<span class="hero"></span>

# Бюджет ДДУС · 2026
`ТМ06` &nbsp; Сводный бюджет (Сд_26), ожидание года (Ожид_26) и факт января–мая · млн руб."""

SEC_YEAR = """### Год: ожидание к сводному бюджету
Ожид_26 = факт января–мая + прогноз июня–декабря"""

SEC_5M = """### Январь–май: факт к сводному бюджету
Исполнение бюджета за 5 месяцев"""

SEC_TABLE = """### Статьи и пояснения по отклонениям
Красным — выше Сд, синим — ниже. Строки «в т.ч.» в суммы не входят."""


def build(api, db_name, schema):
    d = Dashboard(api, "Бюджет ДДУС", "ddus-budget", "ddus_budget", db_name, schema)
    d.dataset(METRICS, LABELS, "Бюджет ДДУС (ТМ06), руб. Метрики — млн руб., без строк «в т.ч.».")

    d.kpi("sd", "Сд_26 · сводный бюджет", "Сд_26", "млн руб.", ",.1f")
    d.kpi("exp", "Ожид_26 · ожидание года", "Ожид_26", "млн руб.", ",.1f")
    d.kpi("dev_pct", "Отклонение", "Откл. Ожид/Сд, %", "Ожид_26 к Сд_26", "+.1%")
    d.kpi("sd5", "Сд, янв–май", "5 мес Сд", "млн руб.", ",.1f")
    d.kpi("f5", "Факт, янв–май", "5 мес Факт", "млн руб.", ",.1f")
    d.kpi("exec5", "Исполнение", "Исполнение 5 мес, %", "факт к Сд", ".1%")

    flt = ("NOT is_detail", NONZERO)
    d.diverging_bar("bars_year", "Отклонение Ожид_26 − Сд_26 по статьям, млн руб.", "article",
                    "Выше Сд (год)", "Ниже Сд (год)", up_label="Выше Сд", down_label="Ниже Сд",
                    filters=flt, sort_metric="Откл. Ожид/Сд")
    d.diverging_bar("bars_5m", "Отклонение факт − Сд за январь–май по статьям, млн руб.", "article",
                    "Выше Сд (5 мес)", "Ниже Сд (5 мес)", up_label="Выше Сд", down_label="Ниже Сд",
                    filters=flt, sort_metric="5 мес Откл.")
    d.table("table", "Статьи оборотов",
            ["activity", "article", "comment"],
            ["Сд_26", "Ожид_26", "Откл. Ожид/Сд", "Откл. Ожид/Сд, %", "5 мес Сд", "5 мес Факт", "5 мес Откл."],
            formats={"Откл. Ожид/Сд": "+,.1f", "Откл. Ожид/Сд, %": "+.1%", "5 мес Откл.": "+,.1f"},
            highlight="Откл. Ожид/Сд", filters=flt, sort_metric="Откл. Ожид/Сд",
            widths={"comment": 440})

    d.row(("md", 12, HEADER), height=14)
    d.row(("md", 6, SEC_YEAR), ("md", 6, SEC_5M), height=10)
    d.row(("sd", 2), ("exp", 2), ("dev_pct", 2), ("sd5", 2), ("f5", 2), ("exec5", 2), height=24)
    d.row(("bars_year", 6), ("bars_5m", 6), height=68)
    d.row(("md", 12, SEC_TABLE), height=10)
    d.row(("table", 12), height=115)

    d.filter("activity", "Деятельность")
    d.filter("article", "Статья оборотов")
    return d.publish()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--db-name", required=True, help="имя подключения к БД в Superset")
    ap.add_argument("--schema", default="public")
    ap.add_argument("--export", help="сохранить ZIP дашборда для импорта")
    a = ap.parse_args()
    api = Superset(a.url, a.user, a.password)
    dash_id = build(api, a.db_name, a.schema)
    if a.export:
        api.export(dash_id, a.export)
    print(f"Готово: {a.url.rstrip('/')}/superset/dashboard/{dash_id}/")
