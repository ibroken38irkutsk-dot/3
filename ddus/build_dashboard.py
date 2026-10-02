"""Создаёт в Superset датасет, графики и дашборд «Бюджет ДДУС» через REST API.

Запуск:
    python build_dashboard.py --url http://superset:8088 --user admin --password *** \
        --db-name "DDUS" [--schema public]

База (--db-name) должна уже быть подключена в Superset, а таблица ddus_budget
загружена (см. etl_ddus.py). Повторный запуск пересоздаёт графики и дашборд.
"""
import argparse
import json
import uuid

import requests

TABLE = "ddus_budget"
DASH_TITLE = "Бюджет ДДУС"
MLN = "1000000.0"

# Сохранённые метрики датасета (в млн руб., без строк «в т.ч.»)
def _s(col):
    return f"SUM(CASE WHEN NOT is_detail THEN {col} ELSE 0 END) / {MLN}"

METRICS = {
    "Сд_26":            (_s("sd_year"), ",.1f"),
    "Ожид_26":          (_s("expected_year"), ",.1f"),
    "Откл. Ожид/Сд":    (f"{_s('expected_year')} - {_s('sd_year')}", "+,.1f"),
    "Откл. Ожид/Сд, %": (f"({_s('expected_year')} - {_s('sd_year')}) / NULLIF({_s('sd_year')}, 0)", "+.1%"),
    "5 мес Сд":         (_s("sd_5m"), ",.1f"),
    "5 мес Факт":       (_s("fact_5m"), ",.1f"),
    "5 мес Откл.":      (f"{_s('fact_5m')} - {_s('sd_5m')}", "+,.1f"),
    "Исполнение 5 мес, %": (f"{_s('fact_5m')} / NULLIF({_s('sd_5m')}, 0)", ".1%"),
    "Июнь-Дек Сд":      (_s("sd_jun_dec"), ",.1f"),
    "Июнь-Дек Прогноз": (_s("forecast_jun_dec"), ",.1f"),
}

COLUMN_LABELS = {
    "activity": "Деятельность",
    "article": "Статья оборотов",
    "parent_article": "Родительская статья",
    "is_detail": "Строка «в т.ч.»",
    "comment": "Пояснения по отклонениям",
}

NONZERO = ("(sd_year <> 0 OR expected_year <> 0 OR sd_5m <> 0 OR fact_5m <> 0)")


def where(sql):
    return {"expressionType": "SQL", "clause": "WHERE", "sqlExpression": sql}


def saved(name):
    return name  # сохранённая метрика датасета передаётся по имени


class API:
    def __init__(self, url, user, password):
        self.url = url.rstrip("/")
        self.s = requests.Session()
        r = self.s.post(f"{self.url}/api/v1/security/login",
                        json={"username": user, "password": password, "provider": "db", "refresh": True})
        r.raise_for_status()
        self.s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        csrf = self.s.get(f"{self.url}/api/v1/security/csrf_token/")
        if csrf.ok:
            self.s.headers["X-CSRFToken"] = csrf.json()["result"]
            self.s.headers["Referer"] = self.url

    def req(self, method, path, **kw):
        r = self.s.request(method, f"{self.url}/api/v1/{path}", **kw)
        if not r.ok:
            raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:500]}")
        return r.json() if r.text else {}

    def find(self, resource, col, value):
        q = json.dumps({"filters": [{"col": col, "opr": "eq", "value": value}]})
        res = self.req("GET", f"{resource}/", params={"q": q})["result"]
        return res[0]["id"] if res else None


def ensure_dataset(api, db_id, schema):
    ds_id = api.find("dataset", "table_name", TABLE)
    if not ds_id:
        ds_id = api.req("POST", "dataset/", json={"database": db_id, "schema": schema, "table_name": TABLE})["id"]
    ds = api.req("GET", f"dataset/{ds_id}")["result"]
    columns = [{"id": c["id"], "column_name": c["column_name"],
                "verbose_name": COLUMN_LABELS.get(c["column_name"]),
                "filterable": True, "groupby": True} for c in ds["columns"]]
    existing = {m["metric_name"]: m["id"] for m in ds["metrics"]}
    metrics = []
    for name, (expr, fmt) in METRICS.items():
        m = {"metric_name": name, "verbose_name": name, "expression": expr, "d3format": fmt}
        if name in existing:
            m["id"] = existing[name]
        metrics.append(m)
    api.req("PUT", f"dataset/{ds_id}?override_columns=false", json={
        "description": "Бюджет ДДУС (ТМ06), руб. Метрики — млн руб., без строк «в т.ч.».",
        "columns": columns, "metrics": metrics,
    })
    return ds_id


def chart(api, ds_id, name, viz, params):
    params = {"datasource": f"{ds_id}__table", "viz_type": viz, **params}
    old = api.find("chart", "slice_name", name)
    if old:
        api.req("DELETE", f"chart/{old}")
    return api.req("POST", "chart/", json={
        "slice_name": name, "viz_type": viz, "datasource_id": ds_id,
        "datasource_type": "table", "params": json.dumps(params, ensure_ascii=False),
    })["id"]


def build_charts(api, ds_id):
    kpi = lambda metric, sub, fmt: {
        "metric": metric, "subheader": sub, "y_axis_format": fmt,
        "header_font_size": 0.3, "subheader_font_size": 0.15, "adhoc_filters": [],
    }
    c = {}
    c["kpi_sd"] = chart(api, ds_id, "ДДУС · Сд_26", "big_number_total", kpi("Сд_26", "млн руб., год", ",.1f"))
    c["kpi_exp"] = chart(api, ds_id, "ДДУС · Ожид_26", "big_number_total", kpi("Ожид_26", "млн руб., год", ",.1f"))
    c["kpi_dev"] = chart(api, ds_id, "ДДУС · Откл. Ожид/Сд", "big_number_total", kpi("Откл. Ожид/Сд", "млн руб.", "+,.1f"))
    c["kpi_dev_pct"] = chart(api, ds_id, "ДДУС · Откл. Ожид/Сд, %", "big_number_total", kpi("Откл. Ожид/Сд, %", "к Сд_26", "+.1%"))
    c["kpi_fact5"] = chart(api, ds_id, "ДДУС · 5 мес Факт", "big_number_total", kpi("5 мес Факт", "млн руб., янв–май", ",.1f"))
    c["kpi_exec5"] = chart(api, ds_id, "ДДУС · Исполнение 5 мес", "big_number_total", kpi("Исполнение 5 мес, %", "Факт / Сд, янв–май", ".1%"))

    def dev_bar(name, metric):
        return chart(api, ds_id, name, "echarts_timeseries_bar", {
            "x_axis": "article", "metrics": [metric], "groupby": [],
            "adhoc_filters": [where("NOT is_detail"), where(NONZERO)],
            "orientation": "horizontal", "x_axis_sort": metric, "x_axis_sort_asc": True,
            "row_limit": 50, "y_axis_format": "+,.1f", "show_value": True,
            "show_legend": False, "rich_tooltip": True, "truncateXAxis": True,
        })

    c["dev_year"] = dev_bar("ДДУС · Отклонение Ожид_26 − Сд_26 по статьям", "Откл. Ожид/Сд")
    c["dev_5m"] = dev_bar("ДДУС · 5 мес: Факт − Сд по статьям", "5 мес Откл.")

    c["table"] = chart(api, ds_id, "ДДУС · Статьи и пояснения", "table", {
        "query_mode": "aggregate", "groupby": ["activity", "article", "comment"],
        "metrics": ["Сд_26", "Ожид_26", "Откл. Ожид/Сд", "Откл. Ожид/Сд, %", "5 мес Сд", "5 мес Факт", "5 мес Откл."],
        "adhoc_filters": [where("NOT is_detail"), where(NONZERO)],
        "timeseries_limit_metric": "Откл. Ожид/Сд", "order_desc": True,
        "row_limit": 200, "server_pagination": False, "include_search": True,
        "table_timestamp_format": "smart_date", "show_cell_bars": False,
        "allow_render_html": False,
        "column_config": {
            "comment": {"columnWidth": 420},
            "Откл. Ожид/Сд": {"d3NumberFormat": "+,.1f"},
            "Откл. Ожид/Сд, %": {"d3NumberFormat": "+.1%"},
            "5 мес Откл.": {"d3NumberFormat": "+,.1f"},
        },
        "conditional_formatting": [
            {"column": "Откл. Ожид/Сд", "operator": ">", "targetValue": 0, "colorScheme": "#C2410C"},
            {"column": "Откл. Ожид/Сд", "operator": "<", "targetValue": 0, "colorScheme": "#047857"},
        ],
    })
    return c


TITLES = {
    "kpi_sd": "Сд_26", "kpi_exp": "Ожид_26", "kpi_dev": "Отклонение Ожид/Сд",
    "kpi_dev_pct": "Отклонение, %", "kpi_fact5": "Факт 5 мес", "kpi_exec5": "Исполнение 5 мес",
    "dev_year": "Отклонение Ожид_26 − Сд_26 по статьям",
    "dev_5m": "5 мес: Факт − Сд по статьям",
    "table": "Статьи и пояснения по отклонениям",
}


def layout(c):
    """position_json: строка KPI, строка из двух графиков, таблица на всю ширину."""
    pos = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": DASH_TITLE}},
    }

    def row(items):
        rid = f"ROW-{uuid.uuid4().hex[:8]}"
        pos[rid] = {"type": "ROW", "id": rid, "children": [], "parents": ["ROOT_ID", "GRID_ID"],
                    "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        pos["GRID_ID"]["children"].append(rid)
        for key, width, height in items:
            cid = f"CHART-{key}"
            pos[cid] = {"type": "CHART", "id": cid, "children": [], "parents": ["ROOT_ID", "GRID_ID", rid],
                        "meta": {"chartId": c[key], "width": width, "height": height,
                                 "sliceNameOverride": TITLES.get(key)}}
            pos[rid]["children"].append(cid)

    row([(k, 2, 26) for k in ["kpi_sd", "kpi_exp", "kpi_dev", "kpi_dev_pct", "kpi_fact5", "kpi_exec5"]])
    row([("dev_year", 6, 70), ("dev_5m", 6, 70)])
    row([("table", 12, 90)])
    return pos


def native_filters(ds_id):
    def f(col, name):
        return {
            "id": f"NATIVE_FILTER-{col}", "name": name, "filterType": "filter_select",
            "targets": [{"datasetId": ds_id, "column": {"name": col}}],
            "controlValues": {"multiSelect": True, "enableEmptyFilter": False, "searchAllOptions": False,
                              "inverseSelection": False},
            "defaultDataMask": {"filterState": {}, "extraFormData": {}, "ownState": {}},
            "cascadeParentIds": [], "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "type": "NATIVE_FILTER", "description": "",
        }
    return [f("activity", "Деятельность"), f("article", "Статья оборотов")]


def build_dashboard(api, ds_id, c):
    old = api.find("dashboard", "dashboard_title", DASH_TITLE)
    if old:
        api.req("DELETE", f"dashboard/{old}")
    meta = {
        "native_filter_configuration": native_filters(ds_id),
        "color_scheme": "supersetColors",
        "label_colors": {"Откл. Ожид/Сд": "#2563EB", "5 мес Откл.": "#0F766E"},
        "refresh_frequency": 0, "cross_filters_enabled": True,
    }
    dash_id = api.req("POST", "dashboard/", json={
        "dashboard_title": DASH_TITLE, "slug": "ddus-budget", "published": True,
        "position_json": json.dumps(layout(c), ensure_ascii=False),
        "json_metadata": json.dumps(meta, ensure_ascii=False),
    })["id"]
    for chart_id in c.values():
        api.req("PUT", f"chart/{chart_id}", json={"dashboards": [dash_id]})
    return dash_id


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--db-name", required=True, help="имя подключения к БД в Superset")
    ap.add_argument("--schema", default="public")
    a = ap.parse_args()
    api = API(a.url, a.user, a.password)
    db_id = api.find("database", "database_name", a.db_name)
    if not db_id:
        raise SystemExit(f"Подключение «{a.db_name}» не найдено в Superset")
    ds_id = ensure_dataset(api, db_id, a.schema)
    charts = build_charts(api, ds_id)
    dash_id = build_dashboard(api, ds_id, charts)
    print(f"Готово: {a.url.rstrip('/')}/superset/dashboard/{dash_id}/")
