"""Общий набор для департаментских дашбордов-одностраничников в Superset.

Всё оформление хранится в самом дашборде (CSS дашборда, цвета в параметрах
графиков), поэтому переезжает вместе с ZIP-экспортом в любой Superset.
SQL метрик — переносимый (CASE/SUM/NULLIF), без функций конкретной СУБД.

Пример спецификации — ddus/build_dashboard.py.
"""
import json
import uuid

import requests

# ---------------------------------------------------------------- палитра
# Проверенная палитра (dataviz reference palette), порядок слотов фиксирован.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
ABOVE = "#e34948"     # выше плана / перерасход (диверг. полюс, тёплый)
BELOW = "#2a78d6"     # ниже плана / экономия (диверг. полюс, холодный)
NEUTRAL = "#b4b2a9"   # план / база сравнения
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"


def rgba(hex_):
    h = hex_.lstrip("#")
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16), "a": 1}


# ---------------------------------------------------------------- стиль
CSS = """
/* ===== Дашборд-одностраничник: общий стиль ===== */
.dashboard-content, .grid-container, .dashboard { background: #f4f4f1; }
.dashboard-component-chart-holder {
  background: #ffffff; border-radius: 12px;
  border: 1px solid rgba(11,11,11,0.07);
  box-shadow: 0 1px 2px rgba(11,11,11,0.04);
  padding: 14px 16px 10px;
}
.dashboard-component-chart-holder .header-title {
  font-size: 13px; font-weight: 600; color: #52514e; letter-spacing: .01em;
}
/* KPI-плитки */
.superset-legacy-chart-big-number .header-line {
  font-weight: 650 !important; color: #0b0b0b; letter-spacing: -0.02em;
}
.superset-legacy-chart-big-number .subheader-line { color: #898781 !important; }
/* Шапка и заголовки разделов (markdown-блоки) */
.dashboard-component-chart-holder:has(.dashboard-markdown),
.dashboard-markdown { background: transparent !important; border: 0 !important; box-shadow: none !important; }
.dashboard-component-chart-holder:has(.hero) { background: #ffffff !important; border: 1px solid rgba(11,11,11,0.07) !important; }
.dashboard-markdown .markdown-container { padding: 4px 4px 0 !important; }
.dashboard-markdown h1 {
  font-size: 26px; font-weight: 700; color: #0b0b0b; margin: 6px 0 2px; letter-spacing: -0.01em;
}
.dashboard-markdown h1 + p { color: #52514e; font-size: 14px; margin: 0; }
.dashboard-markdown h3 {
  font-size: 15px; font-weight: 650; color: #0b0b0b; margin: 10px 0 0;
  padding-left: 10px; border-left: 3px solid #2a78d6; line-height: 1.25;
}
.dashboard-markdown h3 + p { color: #898781; font-size: 12.5px; margin: 4px 0 0 13px; }
.dashboard-markdown code {
  background: #e8eefa; color: #1c5cab; border-radius: 6px; padding: 2px 8px;
  font-family: inherit; font-size: 12px; font-weight: 600;
}
/* Таблица */
.dashboard-component-chart-holder table thead th { color: #52514e; font-weight: 600; }
.dashboard-component-chart-holder table td { font-variant-numeric: tabular-nums; }
"""


# ---------------------------------------------------------------- метрики
def s(col, where=None, scale="1000000.0"):
    """SUM(col) с условием и масштабом (по умолчанию — в миллионы)."""
    body = f"CASE WHEN {where} THEN {col} ELSE 0 END" if where else col
    return f"SUM({body}) / {scale}"


def pos(expr):
    return f"CASE WHEN ({expr}) > 0 THEN ({expr}) ELSE 0 END"


def neg(expr):
    return f"CASE WHEN ({expr}) < 0 THEN ({expr}) ELSE 0 END"


def ratio(a, b):
    return f"({a}) / NULLIF(({b}), 0)"


def where(sql):
    return {"expressionType": "SQL", "clause": "WHERE", "sqlExpression": sql}


# ---------------------------------------------------------------- API
class Superset:
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

    def export(self, dash_id, path):
        r = self.s.get(f"{self.url}/api/v1/dashboard/export/", params={"q": f"!({dash_id})"})
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)


# ---------------------------------------------------------------- дашборд
class Dashboard:
    """Описание одностраничника: датасет, метрики, графики, раскладка."""

    def __init__(self, api, title, slug, table, db_name, schema="public"):
        self.api, self.title, self.slug = api, title, slug
        self.table_name, self.schema = table, schema
        self.db_id = api.find("database", "database_name", db_name)
        if not self.db_id:
            raise SystemExit(f"Подключение «{db_name}» не найдено в Superset")
        self.ds_id = None
        self.charts = {}      # key -> chart id
        self.titles = {}      # key -> заголовок на дашборде
        self.rows = []        # раскладка
        self.filters = []
        self.label_colors = {}

    # --- датасет
    def dataset(self, metrics, column_labels=None, description=""):
        """metrics: {имя: (sql, d3format)}"""
        api, ds_id = self.api, self.api.find("dataset", "table_name", self.table_name)
        if not ds_id:
            ds_id = api.req("POST", "dataset/", json={
                "database": self.db_id, "schema": self.schema, "table_name": self.table_name})["id"]
        ds = api.req("GET", f"dataset/{ds_id}")["result"]
        labels = column_labels or {}
        cols = [{"id": c["id"], "column_name": c["column_name"],
                 "verbose_name": labels.get(c["column_name"]),
                 "filterable": True, "groupby": True} for c in ds["columns"]]
        have = {m["metric_name"]: m["id"] for m in ds["metrics"]}
        ms = []
        for name, (expr, fmt) in metrics.items():
            m = {"metric_name": name, "verbose_name": name, "expression": expr, "d3format": fmt}
            if name in have:
                m["id"] = have[name]
            ms.append(m)
        api.req("PUT", f"dataset/{ds_id}?override_columns=false",
                json={"description": description, "columns": cols, "metrics": ms})
        self.ds_id = ds_id

    # --- графики
    def _chart(self, key, title, viz, params):
        name = f"{self.title} · {title}"
        params = {"datasource": f"{self.ds_id}__table", "viz_type": viz, **params}
        old = self.api.find("chart", "slice_name", name)
        if old:
            self.api.req("DELETE", f"chart/{old}")
        self.charts[key] = self.api.req("POST", "chart/", json={
            "slice_name": name, "viz_type": viz, "datasource_id": self.ds_id,
            "datasource_type": "table", "params": json.dumps(params, ensure_ascii=False),
        })["id"]
        self.titles[key] = title
        return key

    def kpi(self, key, title, metric, sub, fmt, filters=()):
        return self._chart(key, title, "big_number_total", {
            "metric": metric, "subheader": sub, "y_axis_format": fmt,
            "header_font_size": 0.4, "subheader_font_size": 0.125,
            "adhoc_filters": [where(f) for f in filters],
        })

    def diverging_bar(self, key, title, by, up_metric, down_metric, fmt="+,.1f",
                      up_label="Выше плана", down_label="Ниже плана", filters=(), sort_metric=None):
        """Горизонтальные отклонения по категории: вверх — тёплый, вниз — холодный."""
        self.label_colors.update({up_metric: ABOVE, down_metric: BELOW})
        return self._chart(key, title, "echarts_timeseries_bar", {
            "x_axis": by, "metrics": [up_metric, down_metric], "groupby": [],
            "adhoc_filters": [where(f) for f in filters],
            "orientation": "horizontal", "stack": "Stack", "only_total": True,
            "show_value": True, "x_axis_sort": "sum", "x_axis_sort_asc": True,
            "row_limit": 50, "y_axis_format": fmt, "truncateXAxis": True,
            "show_legend": True, "legendOrientation": "top", "legendType": "plain",
            "rich_tooltip": True, "zoomable": False, "minorSplitLine": False,
            "color_scheme": "supersetColors",
        })

    def table(self, key, title, groupby, metrics, formats=None, highlight=None,
              filters=(), sort_metric=None, widths=None):
        cfg = {}
        for m, f in (formats or {}).items():
            cfg.setdefault(m, {})["d3NumberFormat"] = f
        for c, w in (widths or {}).items():
            cfg.setdefault(c, {})["columnWidth"] = w
        cond = []
        if highlight:
            cond = [
                {"column": highlight, "operator": ">", "targetValue": 0, "colorScheme": ABOVE},
                {"column": highlight, "operator": "<", "targetValue": 0, "colorScheme": BELOW},
            ]
        return self._chart(key, title, "table", {
            "query_mode": "aggregate", "groupby": groupby, "metrics": metrics,
            "adhoc_filters": [where(f) for f in filters],
            "timeseries_limit_metric": sort_metric or metrics[0], "order_desc": True,
            "row_limit": 500, "server_pagination": False, "include_search": True,
            "show_cell_bars": False, "allow_render_html": False,
            "column_config": cfg, "conditional_formatting": cond,
        })

    # --- раскладка: строки из графиков и markdown-блоков
    def row(self, *items, height=None):
        """items: ("chart_key", width[, height]) или ("md", width, "текст")"""
        self.rows.append((items, height))

    def filter(self, column, name):
        self.filters.append((column, name))

    def _position(self):
        pos = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
            "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": self.title}},
        }
        for items, row_h in self.rows:
            rid = f"ROW-{uuid.uuid4().hex[:10]}"
            pos[rid] = {"type": "ROW", "id": rid, "children": [], "parents": ["ROOT_ID", "GRID_ID"],
                        "meta": {"background": "BACKGROUND_TRANSPARENT"}}
            pos["GRID_ID"]["children"].append(rid)
            for it in items:
                if it[0] == "md":
                    _, width, text = it
                    cid = f"MARKDOWN-{uuid.uuid4().hex[:10]}"
                    pos[cid] = {"type": "MARKDOWN", "id": cid, "children": [],
                                "parents": ["ROOT_ID", "GRID_ID", rid],
                                "meta": {"width": width, "height": row_h or 12, "code": text}}
                else:
                    key, width = it[0], it[1]
                    h = it[2] if len(it) > 2 else (row_h or 50)
                    cid = f"CHART-{key}"
                    pos[cid] = {"type": "CHART", "id": cid, "children": [],
                                "parents": ["ROOT_ID", "GRID_ID", rid],
                                "meta": {"chartId": self.charts[key], "width": width, "height": h,
                                         "sliceNameOverride": self.titles[key]}}
                pos[rid]["children"].append(cid)
        return pos

    def publish(self):
        api = self.api
        old = api.find("dashboard", "slug", self.slug)
        if old:
            api.req("DELETE", f"dashboard/{old}")
        native = [{
            "id": f"NATIVE_FILTER-{col}", "name": name, "filterType": "filter_select",
            "targets": [{"datasetId": self.ds_id, "column": {"name": col}}],
            "controlValues": {"multiSelect": True, "enableEmptyFilter": False,
                              "searchAllOptions": False, "inverseSelection": False},
            "defaultDataMask": {"filterState": {}, "extraFormData": {}, "ownState": {}},
            "cascadeParentIds": [], "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "type": "NATIVE_FILTER", "description": "",
        } for col, name in self.filters]
        meta = {
            "native_filter_configuration": native,
            "color_scheme": "supersetColors",
            "label_colors": self.label_colors,
            "refresh_frequency": 0, "cross_filters_enabled": True,
        }
        dash_id = api.req("POST", "dashboard/", json={
            "dashboard_title": self.title, "slug": self.slug, "published": True, "css": CSS,
            "position_json": json.dumps(self._position(), ensure_ascii=False),
            "json_metadata": json.dumps(meta, ensure_ascii=False),
        })["id"]
        for cid in self.charts.values():
            api.req("PUT", f"chart/{cid}", json={"dashboards": [dash_id]})
        return dash_id
