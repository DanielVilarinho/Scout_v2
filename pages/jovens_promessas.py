import json
from urllib.parse import urlparse

import numpy as np
import pandas as pd

import dash
from dash import dcc, html, Input, Output, State, callback, no_update, dash_table, ALL
import dash_bootstrap_components as dbc

from data import DF, POS_PT, POSITION_ORDER

dash.register_page(__name__, path="/jovens-promessas", name="Jovens Promessas", order=1)

TOP_LEAGUES = [
    "Bundesliga",
    "Premier League",
    "Ligue 1",
    "LaLiga",
    "Serie A",
    "VriendenLoterij Eredivisie",
    "Liga Portugal Betclic",
]

MARKET_VALUE_BUCKETS = ["<10M", "10M - 20M", "20M - 40M", ">40M"]

ANALYSIS_MODES = [
    {"label": "Rating", "value": "rating"},
    {"label": "Scout Score", "value": "scout_score"},
    {"label": "Elite imediata", "value": "elite_now_score"},
    {"label": "Alto teto", "value": "upside_score"},
    {"label": "Oportunidade", "value": "value_opportunity_score"},
    {"label": "Produção ofensiva", "value": "offensive_score"},
    {"label": "Fit da posição", "value": "position_fit_score"},
    {"label": "Métrica livre", "value": "custom_metric"},
]

QUICK_PRESETS = [
    {"label": "Nenhum", "value": ""},
    {"label": "Sub-20", "value": "sub20"},
    {"label": "Sub-21", "value": "sub21"},
    {"label": "Top ligas", "value": "top_leagues"},
    {"label": "Até 10M", "value": "under_10m"},
    {"label": "Joias escondidas", "value": "hidden_gems"},
    {"label": "1500+ minutos", "value": "min_1500"},
    {"label": "2000+ minutos", "value": "min_2000"},
]

FILTER_OPS = [
    {"label": "=", "value": "eq"},
    {"label": "!=", "value": "ne"},
    {"label": ">", "value": "gt"},
    {"label": ">=", "value": "ge"},
    {"label": "<", "value": "lt"},
    {"label": "<=", "value": "le"},
    {"label": "contém", "value": "contains"},
    {"label": "não contém", "value": "not_contains"},
    {"label": "começa com", "value": "startswith"},
    {"label": "termina com", "value": "endswith"},
    {"label": "é vazio", "value": "is_empty"},
    {"label": "não é vazio", "value": "not_empty"},
]

PAGE_PREFIX = "jp_page"

ID_AGE_MAX = f"{PAGE_PREFIX}_age_max"
ID_MIN_MIN = f"{PAGE_PREFIX}_min_min"
ID_POS = f"{PAGE_PREFIX}_pos"
ID_TOP_LEAGUES = f"{PAGE_PREFIX}_top_leagues"
ID_LEAGUE = f"{PAGE_PREFIX}_league"
ID_COUNTRY = f"{PAGE_PREFIX}_country"
ID_MARKET_VALUE = f"{PAGE_PREFIX}_market_value"
ID_ANALYSIS_MODE = f"{PAGE_PREFIX}_analysis_mode"
ID_METRIC = f"{PAGE_PREFIX}_metric"
ID_TOPN = f"{PAGE_PREFIX}_topn"
ID_VIEW_MODE = f"{PAGE_PREFIX}_view_mode"
ID_QUICK_PRESET = f"{PAGE_PREFIX}_quick_preset"

ID_SUMMARY = f"{PAGE_PREFIX}_summary"
ID_HIDDEN_GEMS = f"{PAGE_PREFIX}_hidden_gems"
ID_RESULTS = f"{PAGE_PREFIX}_results"
ID_COMPARISON_STORE = f"{PAGE_PREFIX}_comparison_store"
ID_COMPARISON_DISPLAY = f"{PAGE_PREFIX}_comparison_display"
ID_CLEAR_COMPARISON = f"{PAGE_PREFIX}_clear_comparison"

ID_MANUAL_FILTERS_STORE = f"{PAGE_PREFIX}_manual_filters_store"
ID_ADD_MANUAL_FILTER = f"{PAGE_PREFIX}_add_manual_filter"

COMPARE_BTN_TYPE = f"{PAGE_PREFIX}_compare_btn"
REMOVE_COMPARE_BTN_TYPE = f"{PAGE_PREFIX}_remove_compare_btn"

MANUAL_FILTER_COL_TYPE = f"{PAGE_PREFIX}_manual_filter_col"
MANUAL_FILTER_OP_TYPE = f"{PAGE_PREFIX}_manual_filter_op"
MANUAL_FILTER_VAL_TYPE = f"{PAGE_PREFIX}_manual_filter_val"
MANUAL_FILTER_REMOVE_TYPE = f"{PAGE_PREFIX}_manual_filter_remove"

df = DF.copy()

if "leaguename" in df.columns:
    df = df[df["leaguename"].astype(str).str.strip() != "Frauen-Bundesliga"].copy()

numeric_cols_base = df.select_dtypes(include="number").columns.tolist()
drop_numeric_like_ids = {"playerid", "teamid", "tournamentid", "seasonid", "dateofbirthtimestamp"}
axis_options = [c for c in numeric_cols_base if c not in drop_numeric_like_ids]
pos_options = [{"label": POS_PT[p], "value": p} for p in POSITION_ORDER if p in POS_PT]


# =========================
# Helpers
# =========================
def _is_int_like(x) -> bool:
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return False
        xf = float(x)
        return np.isfinite(xf) and float(xf).is_integer()
    except Exception:
        return False


def fmt_num(x):
    if x is None:
        return "NA"
    try:
        if pd.isna(x):
            return "NA"
    except Exception:
        pass
    if _is_int_like(x):
        return str(int(float(x)))
    try:
        return f"{float(x):.2f}"
    except Exception:
        return str(x)


def fmt_avg(x):
    if x is None:
        return "NA"
    try:
        if pd.isna(x):
            return "NA"
    except Exception:
        pass
    try:
        return f"{float(x):.2f}"
    except Exception:
        return str(x)


def _fix_image_url(url: str, pid) -> str:
    if not url:
        return ""

    u = str(url).strip()
    if not u:
        return ""

    if u.startswith("//"):
        u = "https:" + u

    if u.startswith("http://"):
        u = "https://" + u[len("http://"):]

    try:
        pr = urlparse(u)
        if not pr.scheme or not pr.netloc:
            return ""
    except Exception:
        return ""

    try:
        pid_str = str(int(float(pid))) if pid is not None and str(pid).strip() != "" else ""
    except Exception:
        pid_str = ""

    if pid_str:
        u = f"{u}&v={pid_str}" if "?" in u else f"{u}?v={pid_str}"

    return u


def _safe_int_from_row(r, col):
    v = r.get(col, np.nan)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        fv = float(v)
        if np.isnan(fv):
            return None
        if float(fv).is_integer():
            return int(fv)
        return int(round(fv))
    except Exception:
        return None


def _safe_float_from_row(r, col):
    v = r.get(col, np.nan)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        fv = float(v)
        if np.isnan(fv):
            return None
        return fv
    except Exception:
        return None


def _parse_market_value(x):
    if x is None:
        return np.nan
    try:
        if pd.isna(x):
            return np.nan
    except Exception:
        pass

    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)

    s = str(x).strip()
    if not s:
        return np.nan

    s = s.replace("€", "").replace("$", "").replace("£", "").replace("R$", "")
    s = s.replace(" ", "").upper()

    mult = 1.0
    if s.endswith("M"):
        mult = 1_000_000.0
        s = s[:-1]
    elif s.endswith("K"):
        mult = 1_000.0
        s = s[:-1]
    elif s.endswith("B"):
        mult = 1_000_000_000.0
        s = s[:-1]

    if "," in s and "." in s:
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")

    try:
        return float(s) * mult
    except Exception:
        return np.nan


def _market_value_bucket(x):
    v = _parse_market_value(x)
    if pd.isna(v):
        return "NA"
    if v < 10_000_000:
        return "<10M"
    if v < 20_000_000:
        return "10M - 20M"
    if v < 40_000_000:
        return "20M - 40M"
    return ">40M"


def _market_value_penalty(bucket: str) -> float:
    if bucket == "<10M":
        return 1.0
    if bucket == "10M - 20M":
        return 0.75
    if bucket == "20M - 40M":
        return 0.45
    if bucket == ">40M":
        return 0.15
    return 0.55


def _market_value_badge_style(bucket: str):
    base = {
        "fontSize": "11px",
        "padding": "4px 10px",
        "borderRadius": "999px",
        "display": "inline-block",
        "fontWeight": "600",
        "border": "1px solid transparent",
    }

    styles = {
        "<10M": {
            "background": "rgba(40,167,69,0.10)",
            "color": "#198754",
            "border": "1px solid rgba(25,135,84,0.25)",
        },
        "10M - 20M": {
            "background": "rgba(13,110,253,0.10)",
            "color": "#0d6efd",
            "border": "1px solid rgba(13,110,253,0.25)",
        },
        "20M - 40M": {
            "background": "rgba(255,193,7,0.15)",
            "color": "#b58100",
            "border": "1px solid rgba(181,129,0,0.25)",
        },
        ">40M": {
            "background": "rgba(220,53,69,0.10)",
            "color": "#dc3545",
            "border": "1px solid rgba(220,53,69,0.25)",
        },
        "NA": {
            "background": "rgba(108,117,125,0.10)",
            "color": "#6c757d",
            "border": "1px solid rgba(108,117,125,0.20)",
        },
    }

    base.update(styles.get(bucket, styles["NA"]))
    return base


def _league_badge_style(is_top_league: bool):
    if is_top_league:
        return {
            "fontSize": "11px",
            "padding": "4px 10px",
            "borderRadius": "999px",
            "display": "inline-block",
            "fontWeight": "600",
            "background": "linear-gradient(135deg, rgba(111,66,193,0.18), rgba(13,110,253,0.16))",
            "color": "#4b2ca0",
            "border": "1px solid rgba(111,66,193,0.22)",
        }
    return {
        "fontSize": "11px",
        "padding": "4px 10px",
        "borderRadius": "999px",
        "display": "inline-block",
        "fontWeight": "600",
        "background": "rgba(108,117,125,0.08)",
        "color": "#6c757d",
        "border": "1px solid rgba(108,117,125,0.18)",
    }


def _context_badge(label: str, kind: str = "neutral"):
    styles = {
        "purple": {"background": "rgba(111,66,193,0.10)", "color": "#6f42c1", "border": "1px solid rgba(111,66,193,0.18)"},
        "blue": {"background": "rgba(13,110,253,0.10)", "color": "#0d6efd", "border": "1px solid rgba(13,110,253,0.18)"},
        "green": {"background": "rgba(25,135,84,0.10)", "color": "#198754", "border": "1px solid rgba(25,135,84,0.18)"},
        "gold": {"background": "rgba(255,193,7,0.16)", "color": "#9a7000", "border": "1px solid rgba(181,129,0,0.20)"},
        "red": {"background": "rgba(220,53,69,0.10)", "color": "#dc3545", "border": "1px solid rgba(220,53,69,0.18)"},
        "neutral": {"background": "rgba(108,117,125,0.08)", "color": "#6c757d", "border": "1px solid rgba(108,117,125,0.16)"},
    }
    st = styles.get(kind, styles["neutral"])
    return html.Span(
        label,
        style={
            "fontSize": "10px",
            "padding": "4px 9px",
            "borderRadius": "999px",
            "display": "inline-block",
            "fontWeight": "700",
            "marginRight": "6px",
            "marginBottom": "6px",
            **st,
        },
    )


def _quick_stat_chip(label: str, value: str):
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(
                        label,
                        className="text-muted",
                        style={
                            "fontSize": "10px",
                            "lineHeight": "10px",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.4px",
                        },
                    ),
                    html.Div(
                        value,
                        className="fw-bold",
                        style={"fontSize": "16px", "lineHeight": "18px", "marginTop": "4px"},
                    ),
                ],
                className="p-2",
            ),
            className="h-100 border-0",
            style={
                "borderRadius": "14px",
                "background": "linear-gradient(180deg, rgba(255,255,255,0.95), rgba(248,249,250,0.95))",
                "boxShadow": "0 2px 10px rgba(16,24,40,0.05)",
            },
        ),
        xs=4,
    )


def _summary_kpi(title: str, value: str, subtitle: str | None = None):
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(title, className="text-muted", style={"fontSize": "11px", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
                    html.Div(value, className="fw-bold", style={"fontSize": "24px", "lineHeight": "26px", "marginTop": "6px"}),
                    html.Div(subtitle or "", className="text-muted", style={"fontSize": "12px", "marginTop": "4px"}),
                ]
            ),
            className="h-100 border-0",
            style={
                "borderRadius": "20px",
                "background": "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.98))",
                "boxShadow": "0 10px 24px rgba(16,24,40,0.06)",
            },
        ),
        xl=2,
        lg=4,
        md=6,
        sm=6,
    )


def _empty_cover():
    return html.Div(
        [html.Div("Sem Foto", className="fw-semibold", style={"fontSize": "12px"})],
        style={
            "width": "78px",
            "height": "78px",
            "borderRadius": "16px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "background": "linear-gradient(135deg, #eef2ff, #f8f9fa)",
            "color": "#6c757d",
            "border": "1px solid rgba(108,117,125,0.12)",
            "textAlign": "center",
        },
    )


def _safe_series(df_in: pd.DataFrame, col: str) -> pd.Series:
    if col in df_in.columns:
        return pd.to_numeric(df_in[col], errors="coerce")
    return pd.Series(np.nan, index=df_in.index)


def _minmax_0_1(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series(0.0, index=s.index)
    mn = s.min(skipna=True)
    mx = s.max(skipna=True)
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return pd.Series(0.5, index=s.index)
    return ((s - mn) / (mx - mn)).fillna(0.0)


def _positions_text(row):
    lst = row.get("positions_list", [])
    if isinstance(lst, list) and lst:
        vals = [str(x) for x in lst[:3]]
        return " | ".join(vals)
    return ""


def _position_family_from_selection(positions):
    if not positions:
        return "generic"

    ps = [str(p).upper() for p in positions]

    if any(p in {"GK"} for p in ps):
        return "gk"
    if any(p in {"ST", "CF", "SS"} for p in ps):
        return "attack"
    if any(p in {"RW", "LW", "RF", "LF"} for p in ps):
        return "wing"
    if any(p in {"AM", "CAM", "RAM", "LAM", "OM"} for p in ps):
        return "am"
    if any(p in {"DM", "CDM", "CM", "RCM", "LCM", "RM", "LM"} for p in ps):
        return "mid"
    if any(p in {"CB", "RCB", "LCB", "RB", "LB", "RWB", "LWB", "WB", "SW"} for p in ps):
        return "def"
    return "generic"


def _prepare_scores(base_df: pd.DataFrame) -> pd.DataFrame:
    out = base_df.copy()

    if "proposedmarketvalue" in out.columns:
        out["market_value_bucket"] = out["proposedmarketvalue"].apply(_market_value_bucket)
        out["market_value_num"] = out["proposedmarketvalue"].apply(_parse_market_value)
    else:
        out["market_value_bucket"] = "NA"
        out["market_value_num"] = np.nan

    out["is_top_league"] = out["leaguename"].astype(str).isin(TOP_LEAGUES) if "leaguename" in out.columns else False

    age_s = _safe_series(out, "age")
    min_s = _safe_series(out, "minutesplayed")
    rating_s = _safe_series(out, "rating")
    goals_s = _safe_series(out, "goals")
    assists_s = _safe_series(out, "assists")
    xg_s = _safe_series(out, "xg")
    xa_s = _safe_series(out, "xa")

    offensive_raw = goals_s.fillna(0) + assists_s.fillna(0) + (xg_s.fillna(0) * 0.7) + (xa_s.fillna(0) * 0.7)

    age_young = 1 - _minmax_0_1(age_s)
    minutes_norm = _minmax_0_1(min_s)
    rating_norm = _minmax_0_1(rating_s)
    offensive_norm = _minmax_0_1(offensive_raw)
    top_league_norm = out["is_top_league"].astype(int).astype(float)
    market_norm = out["market_value_bucket"].map(_market_value_penalty).fillna(0.55)

    out["offensive_score"] = (
        0.35 * rating_norm +
        0.45 * offensive_norm +
        0.20 * minutes_norm
    ) * 100

    out["upside_score"] = (
        0.40 * age_young +
        0.20 * rating_norm +
        0.15 * minutes_norm +
        0.15 * offensive_norm +
        0.10 * market_norm
    ) * 100

    out["elite_now_score"] = (
        0.38 * rating_norm +
        0.25 * minutes_norm +
        0.18 * offensive_norm +
        0.14 * top_league_norm +
        0.05 * age_young
    ) * 100

    out["value_opportunity_score"] = (
        0.30 * market_norm +
        0.25 * rating_norm +
        0.20 * offensive_norm +
        0.15 * age_young +
        0.10 * minutes_norm
    ) * 100

    out["scout_score"] = (
        0.30 * rating_norm +
        0.20 * age_young +
        0.16 * minutes_norm +
        0.16 * offensive_norm +
        0.10 * market_norm +
        0.08 * top_league_norm
    ) * 100

    return out


def _apply_position_fit_score(base_df: pd.DataFrame, positions) -> pd.DataFrame:
    out = base_df.copy()
    fam = _position_family_from_selection(positions)

    age_young = 1 - _minmax_0_1(_safe_series(out, "age"))
    minutes_norm = _minmax_0_1(_safe_series(out, "minutesplayed"))
    rating_norm = _minmax_0_1(_safe_series(out, "rating"))
    offensive_norm = _minmax_0_1(_safe_series(out, "offensive_score"))
    scout_norm = _minmax_0_1(_safe_series(out, "scout_score"))

    if fam == "gk":
        score = 0.45 * rating_norm + 0.35 * minutes_norm + 0.20 * age_young
    elif fam == "def":
        score = 0.34 * rating_norm + 0.30 * minutes_norm + 0.16 * scout_norm + 0.15 * age_young + 0.05 * offensive_norm
    elif fam in {"mid", "am"}:
        score = 0.28 * rating_norm + 0.22 * minutes_norm + 0.20 * offensive_norm + 0.15 * scout_norm + 0.15 * age_young
    elif fam in {"wing", "attack"}:
        score = 0.36 * offensive_norm + 0.25 * rating_norm + 0.15 * minutes_norm + 0.14 * age_young + 0.10 * scout_norm
    else:
        score = 0.30 * rating_norm + 0.20 * age_young + 0.20 * minutes_norm + 0.15 * offensive_norm + 0.15 * scout_norm

    out["position_fit_score"] = score * 100
    return out


def _apply_single_dynamic_filter(out: pd.DataFrame, col: str | None, op: str | None, val: str | None) -> pd.DataFrame:
    if not col or col not in out.columns or not op:
        return out

    s = out[col]

    if op == "is_empty":
        return out[s.isna() | (s.astype(str).str.strip() == "")]
    if op == "not_empty":
        return out[~(s.isna() | (s.astype(str).str.strip() == ""))]

    is_num_col = pd.api.types.is_numeric_dtype(s)

    if is_num_col and op in {"eq", "ne", "gt", "ge", "lt", "le"}:
        try:
            v = float(val) if val is not None and str(val).strip() != "" else None
        except Exception:
            v = None

        if v is None:
            return out

        sn = pd.to_numeric(s, errors="coerce")

        if op == "eq":
            return out[sn == v]
        if op == "ne":
            return out[sn != v]
        if op == "gt":
            return out[sn > v]
        if op == "ge":
            return out[sn >= v]
        if op == "lt":
            return out[sn < v]
        if op == "le":
            return out[sn <= v]

    st = s.astype(str).fillna("").str.strip()
    vtxt = "" if val is None else str(val).strip()

    if op == "eq":
        return out[st == vtxt]
    if op == "ne":
        return out[st != vtxt]
    if op == "contains":
        return out[st.str.contains(vtxt, case=False, na=False)]
    if op == "not_contains":
        return out[~st.str.contains(vtxt, case=False, na=False)]
    if op == "startswith":
        return out[st.str.lower().str.startswith(vtxt.lower())]
    if op == "endswith":
        return out[st.str.lower().str.endswith(vtxt.lower())]

    return out


def _apply_dynamic_filters(out: pd.DataFrame, manual_filters: list[dict] | None) -> pd.DataFrame:
    result = out.copy()
    for f in (manual_filters or []):
        result = _apply_single_dynamic_filter(
            result,
            f.get("col"),
            f.get("op"),
            f.get("val"),
        )
    return result


def _build_context_badges(row):
    badges = []

    age = _safe_float_from_row(row, "age")
    minutes = _safe_float_from_row(row, "minutesplayed")
    mv_bucket = str(row.get("market_value_bucket", "NA")).strip() or "NA"
    is_top_league = bool(row.get("is_top_league", False))
    rating = _safe_float_from_row(row, "rating")
    offensive = _safe_float_from_row(row, "offensive_score")

    if age is not None and age <= 19:
        badges.append(_context_badge("Sub-20", "purple"))
    elif age is not None and age <= 21:
        badges.append(_context_badge("Sub-21", "blue"))

    if minutes is not None and minutes >= 2000:
        badges.append(_context_badge("Amostra forte", "green"))
    elif minutes is not None and minutes >= 1200:
        badges.append(_context_badge("Boa minutagem", "blue"))

    if mv_bucket == "<10M":
        badges.append(_context_badge("Baixo custo", "green"))
    elif mv_bucket == "10M - 20M":
        badges.append(_context_badge("Custo controlado", "blue"))

    if is_top_league:
        badges.append(_context_badge("Top Liga", "purple"))

    if (
        not is_top_league
        and mv_bucket in {"<10M", "10M - 20M"}
        and rating is not None and rating >= 7
        and minutes is not None and minutes >= 900
    ):
        badges.append(_context_badge("Joia escondida", "gold"))

    if offensive is not None and offensive >= 70:
        badges.append(_context_badge("Ameaça ofensiva", "red"))

    return badges[:5]


def _player_insight(row):
    age = _safe_float_from_row(row, "age")
    minutes = _safe_float_from_row(row, "minutesplayed")
    rating = _safe_float_from_row(row, "rating")
    mv_bucket = str(row.get("market_value_bucket", "NA")).strip() or "NA"
    is_top_league = bool(row.get("is_top_league", False))

    if age is not None and age <= 19 and minutes is not None and minutes >= 1200:
        return "Muito jovem e já com amostra competitiva relevante."
    if is_top_league and rating is not None and rating >= 7:
        return "Já performa em contexto de liga forte."
    if mv_bucket == "<10M" and rating is not None and rating >= 7:
        return "Perfil claro de oportunidade de mercado."
    if minutes is not None and minutes < 900:
        return "Mostra upside, mas ainda com amostra mais curta."
    return "Nome consistente para shortlist de monitoramento."


def _ranking_badge(idx):
    if idx == 1:
        return html.Span("🥇", style={"fontSize": "20px"})
    if idx == 2:
        return html.Span("🥈", style={"fontSize": "20px"})
    if idx == 3:
        return html.Span("🥉", style={"fontSize": "20px"})
    return html.Span(f"#{idx}", style={"fontSize": "12px", "fontWeight": "700", "color": "#6f42c1"})


def _card_shadow(idx):
    if idx == 1:
        return "0 12px 30px rgba(111,66,193,0.18)"
    if idx == 2:
        return "0 12px 30px rgba(13,110,253,0.16)"
    if idx == 3:
        return "0 12px 30px rgba(181,129,0,0.16)"
    return "0 12px 28px rgba(16,24,40,0.08)"


def _render_manual_filter_rows(filters_data):
    rows = []

    for i, _ in enumerate(filters_data or []):
        rows.append(
            dbc.Card(
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label("Coluna / KPI", className="fw-semibold small"),
                                        dcc.Dropdown(
                                            id={"type": MANUAL_FILTER_COL_TYPE, "index": i},
                                            options=dynamic_col_options,
                                            value=(filters_data[i].get("col") if i < len(filters_data) else None),
                                            placeholder="Escolha uma coluna",
                                        ),
                                    ],
                                    md=4
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Operador", className="fw-semibold small"),
                                        dcc.Dropdown(
                                            id={"type": MANUAL_FILTER_OP_TYPE, "index": i},
                                            options=FILTER_OPS,
                                            value=(filters_data[i].get("op") if i < len(filters_data) else None),
                                            placeholder="Escolha um operador",
                                        ),
                                    ],
                                    md=3
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Valor", className="fw-semibold small"),
                                        dcc.Input(
                                            id={"type": MANUAL_FILTER_VAL_TYPE, "index": i},
                                            type="text",
                                            value=(filters_data[i].get("val") if i < len(filters_data) else ""),
                                            placeholder="Ex: 7.0, Brazil, 1500...",
                                            style={"width": "100%"},
                                        ),
                                    ],
                                    md=4
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Ação", className="fw-semibold small"),
                                        dbc.Button(
                                            "Remover",
                                            id={"type": MANUAL_FILTER_REMOVE_TYPE, "index": i},
                                            color="danger",
                                            outline=True,
                                            className="w-100",
                                            n_clicks=0,
                                            style={"borderRadius": "12px", "fontWeight": "600"},
                                        ),
                                    ],
                                    md=1
                                ),
                            ],
                            className="g-3 align-items-end",
                        )
                    ]
                ),
                className="border-0 mb-3",
                style={
                    "borderRadius": "18px",
                    "background": "rgba(248,250,252,0.75)",
                    "boxShadow": "0 6px 18px rgba(16,24,40,0.04)",
                },
            )
        )

    if not rows:
        return dbc.Alert(
            "Nenhum filtro manual adicionado ainda. Clique em “Adicionar filtro manual”.",
            color="light",
            class_name="mb-0"
        )

    return rows


df = _prepare_scores(df)

derived_metric_options = [
    "rating",
    "scout_score",
    "elite_now_score",
    "upside_score",
    "value_opportunity_score",
    "offensive_score",
    "position_fit_score",
]

metric_options = sorted(set(axis_options + derived_metric_options))

league_options = []
if "leaguename" in df.columns:
    leagues = (
        df["leaguename"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda s: (s != "") & (s != "Frauen-Bundesliga")]
        .unique()
        .tolist()
    )
    leagues = sorted(leagues)
    league_options = [{"label": l, "value": l} for l in leagues]

country_options = []
if "playercountry" in df.columns:
    countries = (
        df["playercountry"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda s: s != ""]
        .unique()
        .tolist()
    )
    countries = sorted(countries)
    country_options = [{"label": c, "value": c} for c in countries]

market_value_options = [{"label": b, "value": b} for b in MARKET_VALUE_BUCKETS]
dynamic_cols = [c for c in df.columns if c not in {"positions_list"}]
dynamic_col_options = [{"label": c, "value": c} for c in dynamic_cols]


# =========================
# Core
# =========================
def get_filtered_universe(
    dff: pd.DataFrame,
    age_max: int = 23,
    min_minutes: int = 1000,
    positions: list[str] | None = None,
    leagues: list[str] | None = None,
    countries: list[str] | None = None,
    market_value_ranges: list[str] | None = None,
    manual_filters: list[dict] | None = None,
) -> pd.DataFrame:
    out = dff.copy()

    if "leaguename" in out.columns:
        out = out[out["leaguename"].astype(str).str.strip() != "Frauen-Bundesliga"]

    if "age" in out.columns:
        out = out[out["age"].fillna(999) <= int(age_max)]

    if "minutesplayed" in out.columns:
        out = out[out["minutesplayed"].fillna(-1) >= int(min_minutes)]

    if positions:
        sel = {str(p).upper() for p in positions}
        if "positions_list" in out.columns:
            out = out[out["positions_list"].apply(lambda lst: any(str(p).upper() in sel for p in (lst or [])))]

    if leagues and "leaguename" in out.columns:
        leagues_set = {str(l).strip() for l in leagues if str(l).strip() != ""}
        if leagues_set:
            out = out[out["leaguename"].astype(str).isin(leagues_set)]

    if countries and "playercountry" in out.columns:
        countries_set = {str(c).strip() for c in countries if str(c).strip() != ""}
        if countries_set:
            out = out[out["playercountry"].astype(str).isin(countries_set)]

    if market_value_ranges and "market_value_bucket" in out.columns:
        mv_set = {str(v).strip() for v in market_value_ranges if str(v).strip() != ""}
        if mv_set:
            out = out[out["market_value_bucket"].isin(mv_set)]

    out = _apply_dynamic_filters(out, manual_filters)

    return out.copy()


def get_hidden_gems(dff: pd.DataFrame, metric: str):
    out = dff.copy()
    if out.empty:
        return out

    cond = (
        (~out["is_top_league"].fillna(False))
        & (out["market_value_bucket"].isin(["<10M", "10M - 20M"]))
    )

    if "minutesplayed" in out.columns:
        cond = cond & (pd.to_numeric(out["minutesplayed"], errors="coerce").fillna(0) >= 900)

    if "age" in out.columns:
        cond = cond & (pd.to_numeric(out["age"], errors="coerce").fillna(99) <= 22)

    out = out[cond].copy()

    if metric in out.columns:
        out = out.dropna(subset=[metric]).sort_values(metric, ascending=False)

    return out.head(4)


# =========================
# Layout
# =========================
layout = dbc.Container(
    fluid=True,
    children=[
        dcc.Store(id=ID_COMPARISON_STORE, storage_type="memory", data=[]),
        dcc.Store(id=ID_MANUAL_FILTERS_STORE, storage_type="memory", data=[]),

        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    "SCOUTING | TALENT ID",
                                    className="fw-semibold",
                                    style={
                                        "fontSize": "12px",
                                        "letterSpacing": "1px",
                                        "color": "#6f42c1",
                                        "textTransform": "uppercase",
                                    },
                                ),
                                html.H2("Jovens Promessas", className="mb-1 fw-bold"),
                                html.Div(
                                    "Página completa de talento: score composto, badges contextuais, atalhos, tabela ordenável, joias escondidas e comparação SofaScore.",
                                    className="text-muted",
                                ),
                            ],
                            style={
                                "padding": "20px 24px",
                                "borderRadius": "24px",
                                "background": "linear-gradient(135deg, rgba(111,66,193,0.10), rgba(13,110,253,0.08), rgba(255,255,255,0.96))",
                                "border": "1px solid rgba(111,66,193,0.12)",
                                "boxShadow": "0 10px 28px rgba(16,24,40,0.05)",
                            },
                        )
                    ],
                    className="py-3",
                )
            )
        ),

        dbc.Card(
            className="mb-4 border-0",
            style={
                "borderRadius": "24px",
                "boxShadow": "0 10px 30px rgba(16,24,40,0.07)",
                "background": "rgba(255,255,255,0.97)",
            },
            children=[
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div("Filtros e contexto de análise", className="fw-bold", style={"fontSize": "18px"}),
                                    md=6
                                ),
                                dbc.Col(
                                    html.Div("Tudo organizado em blocos para leitura mais limpa.", className="text-muted text-md-end"),
                                    md=6
                                ),
                            ],
                            className="mb-3 align-items-center",
                        ),

                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Card(
                                        dbc.CardBody(
                                            [
                                                html.Div("Recorte base", className="fw-semibold mb-3", style={"fontSize": "15px"}),
                                                html.Label("Idade máxima", className="fw-semibold small"),
                                                dcc.Slider(
                                                    id=ID_AGE_MAX,
                                                    min=16,
                                                    max=25,
                                                    step=1,
                                                    value=23,
                                                    marks={16: "16", 18: "18", 20: "20", 23: "23", 25: "25"},
                                                    tooltip={"placement": "bottom", "always_visible": False},
                                                ),
                                                html.Div("Até qual idade considerar.", className="text-muted small mt-1 mb-3"),

                                                html.Label("Minutos mínimos", className="fw-semibold small"),
                                                dcc.Slider(
                                                    id=ID_MIN_MIN,
                                                    min=0,
                                                    max=3000,
                                                    step=50,
                                                    value=1000,
                                                    marks={0: "0", 500: "500", 1000: "1000", 2000: "2000", 3000: "3000"},
                                                    tooltip={"placement": "bottom", "always_visible": False},
                                                ),
                                                html.Div("Evita amostras muito curtas.", className="text-muted small mt-1 mb-3"),

                                                html.Label("Posição", className="fw-semibold small"),
                                                dcc.Dropdown(
                                                    id=ID_POS,
                                                    options=pos_options,
                                                    value=None,
                                                    multi=True,
                                                    placeholder="Todas as posições",
                                                ),
                                                html.Div("Filtra pela lista de posições.", className="text-muted small mt-1"),
                                            ]
                                        ),
                                        className="h-100 border-0",
                                        style={"borderRadius": "20px", "background": "rgba(248,250,252,0.85)"},
                                    ),
                                    lg=4,
                                    md=12,
                                    className="mb-3 mb-lg-0",
                                ),
                                dbc.Col(
                                    dbc.Card(
                                        dbc.CardBody(
                                            [
                                                html.Div("Contexto competitivo", className="fw-semibold mb-3", style={"fontSize": "15px"}),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label("Liga", className="fw-semibold small"),
                                                                dcc.Dropdown(
                                                                    id=ID_LEAGUE,
                                                                    options=league_options,
                                                                    value=None,
                                                                    multi=True,
                                                                    placeholder=("Todas as ligas" if league_options else "Sem coluna leaguename"),
                                                                    disabled=(not bool(league_options)),
                                                                ),
                                                            ],
                                                            md=8,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label("Top Ligas", className="fw-semibold small"),
                                                                dbc.Checklist(
                                                                    id=ID_TOP_LEAGUES,
                                                                    options=[{"label": "Auto", "value": "top"}],
                                                                    value=[],
                                                                    switch=True,
                                                                    className="mt-2",
                                                                ),
                                                            ],
                                                            md=4,
                                                        ),
                                                    ],
                                                    className="g-3 mb-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label("Nacionalidade", className="fw-semibold small"),
                                                                dcc.Dropdown(
                                                                    id=ID_COUNTRY,
                                                                    options=country_options,
                                                                    value=None,
                                                                    multi=True,
                                                                    placeholder=("Todos os países" if country_options else "Sem coluna country"),
                                                                    disabled=(not bool(country_options)),
                                                                ),
                                                            ],
                                                            md=6,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label("Market value", className="fw-semibold small"),
                                                                dcc.Dropdown(
                                                                    id=ID_MARKET_VALUE,
                                                                    options=market_value_options,
                                                                    value=None,
                                                                    multi=True,
                                                                    placeholder=("Todas as faixas" if market_value_options else "Sem coluna proposedmarketvalue"),
                                                                    disabled=(not bool(market_value_options)),
                                                                ),
                                                            ],
                                                            md=6,
                                                        ),
                                                    ],
                                                    className="g-3",
                                                ),
                                            ]
                                        ),
                                        className="h-100 border-0",
                                        style={"borderRadius": "20px", "background": "rgba(248,250,252,0.85)"},
                                    ),
                                    lg=4,
                                    md=12,
                                    className="mb-3 mb-lg-0",
                                ),
                                dbc.Col(
                                    dbc.Card(
                                        dbc.CardBody(
                                            [
                                                html.Div("Ranking e atalhos", className="fw-semibold mb-3", style={"fontSize": "15px"}),
                                                html.Label("Modo de análise", className="fw-semibold small"),
                                                dcc.Dropdown(
                                                    id=ID_ANALYSIS_MODE,
                                                    options=ANALYSIS_MODES,
                                                    value="rating",
                                                    clearable=False,
                                                ),
                                                html.Div("Define o tipo de promessa que você quer destacar.", className="text-muted small mt-1 mb-3"),

                                                html.Label("Ordenar por", className="fw-semibold small"),
                                                dcc.Dropdown(
                                                    id=ID_METRIC,
                                                    options=[{"label": c, "value": c} for c in metric_options],
                                                    value="rating",
                                                    clearable=False,
                                                ),
                                                html.Div("Use scores compostos ou qualquer métrica disponível.", className="text-muted small mt-1 mb-3"),

                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label("Atalho rápido", className="fw-semibold small"),
                                                                dcc.Dropdown(
                                                                    id=ID_QUICK_PRESET,
                                                                    options=QUICK_PRESETS,
                                                                    value="",
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            md=8,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label("Top N", className="fw-semibold small"),
                                                                dcc.Dropdown(
                                                                    id=ID_TOPN,
                                                                    options=[{"label": str(n), "value": n} for n in [6, 12, 18, 24, 30, 36, 48, 60, 100]],
                                                                    value=60,
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            md=4,
                                                        ),
                                                    ],
                                                    className="g-3 mb-3",
                                                ),

                                                html.Label("Visualização", className="fw-semibold small"),
                                                dbc.RadioItems(
                                                    id=ID_VIEW_MODE,
                                                    options=[
                                                        {"label": "Cards", "value": "cards"},
                                                        {"label": "Tabela comparativa", "value": "table"},
                                                    ],
                                                    value="cards",
                                                    inline=True,
                                                    inputClassName="me-2",
                                                    labelClassName="me-3",
                                                ),
                                            ]
                                        ),
                                        className="h-100 border-0",
                                        style={"borderRadius": "20px", "background": "rgba(248,250,252,0.85)"},
                                    ),
                                    lg=4,
                                    md=12,
                                ),
                            ],
                            className="g-3",
                        ),

                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    title="Filtros manuais por KPI / coluna",
                                    children=[
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Adicionar filtro manual",
                                                        id=ID_ADD_MANUAL_FILTER,
                                                        color="primary",
                                                        className="mb-3",
                                                        style={"borderRadius": "12px", "fontWeight": "600"},
                                                    ),
                                                    md=12
                                                ),
                                            ]
                                        ),
                                        html.Div(id=f"{PAGE_PREFIX}_manual_filters_container"),
                                    ],
                                )
                            ],
                            start_collapsed=True,
                            flush=False,
                            className="mt-3",
                        ),
                    ]
                )
            ],
        ),

        html.Div(id=ID_SUMMARY, className="mb-4"),

        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            html.Div("Área de comparação (Máximo 4)", className="fw-bold mb-2", style={"fontSize": "17px"}),
                                            md=8,
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Limpar comparações",
                                                id=ID_CLEAR_COMPARISON,
                                                color="secondary",
                                                outline=True,
                                                className="w-100",
                                                style={"borderRadius": "12px", "fontWeight": "600"},
                                            ),
                                            md=4,
                                        ),
                                    ],
                                    className="g-2 align-items-center mb-2",
                                ),
                                html.Div(id=ID_COMPARISON_DISPLAY),
                            ]
                        ),
                        className="border-0 h-100",
                        style={"borderRadius": "24px", "boxShadow": "0 12px 28px rgba(16,24,40,0.08)"},
                    ),
                    md=12,
                    className="mb-4",
                ),
            ],
            className="g-4",
        ),

        dbc.Row(
            [
                dbc.Col(
                    html.Div(id=ID_HIDDEN_GEMS),
                    md=12,
                    className="mb-4",
                ),
            ],
            className="g-4",
        ),

        html.Div(id=ID_RESULTS),
    ],
    style={"maxWidth": "1680px", "paddingBottom": "24px"},
)


# =========================
# Manual filters callbacks
# =========================
@callback(
    Output(ID_MANUAL_FILTERS_STORE, "data"),
    Input(ID_ADD_MANUAL_FILTER, "n_clicks"),
    Input({"type": MANUAL_FILTER_REMOVE_TYPE, "index": ALL}, "n_clicks"),
    State(ID_MANUAL_FILTERS_STORE, "data"),
    prevent_initial_call=True,
)
def manage_manual_filters(add_clicks, remove_clicks, filters_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update

    filters_data = filters_data or []
    triggered = ctx.triggered[0]
    prop_id = triggered["prop_id"].split(".")[0]
    prop_value = triggered.get("value", None)

    if prop_id == ID_ADD_MANUAL_FILTER:
        if not prop_value:
            return no_update
        new_filters = list(filters_data)
        new_filters.append({"col": None, "op": None, "val": ""})
        return new_filters

    try:
        payload = json.loads(prop_id)
        if payload.get("type") == MANUAL_FILTER_REMOVE_TYPE and prop_value not in (None, 0):
            idx = int(payload.get("index"))
            return [f for i, f in enumerate(filters_data) if i != idx]
    except Exception:
        return no_update

    return no_update


@callback(
    Output(ID_MANUAL_FILTERS_STORE, "data", allow_duplicate=True),
    Input({"type": MANUAL_FILTER_COL_TYPE, "index": ALL}, "value"),
    Input({"type": MANUAL_FILTER_OP_TYPE, "index": ALL}, "value"),
    Input({"type": MANUAL_FILTER_VAL_TYPE, "index": ALL}, "value"),
    State(ID_MANUAL_FILTERS_STORE, "data"),
    prevent_initial_call=True,
)
def sync_manual_filters(cols, ops, vals, filters_data):
    filters_data = filters_data or []
    max_len = max(len(cols or []), len(ops or []), len(vals or []), len(filters_data))

    out = []
    for i in range(max_len):
        out.append(
            {
                "col": cols[i] if i < len(cols or []) else (filters_data[i].get("col") if i < len(filters_data) else None),
                "op": ops[i] if i < len(ops or []) else (filters_data[i].get("op") if i < len(filters_data) else None),
                "val": vals[i] if i < len(vals or []) else (filters_data[i].get("val") if i < len(filters_data) else ""),
            }
        )
    return out


@callback(
    Output(f"{PAGE_PREFIX}_manual_filters_container", "children"),
    Input(ID_MANUAL_FILTERS_STORE, "data"),
)
def render_manual_filters(filters_data):
    return _render_manual_filter_rows(filters_data)


# =========================
# Callback: atalhos rápidos
# =========================
@callback(
    Output(ID_AGE_MAX, "value"),
    Output(ID_MIN_MIN, "value"),
    Output(ID_MARKET_VALUE, "value"),
    Output(ID_TOP_LEAGUES, "value"),
    Input(ID_QUICK_PRESET, "value"),
    prevent_initial_call=True,
)
def apply_quick_preset(preset):
    if not preset:
        return no_update, no_update, no_update, no_update

    if preset == "sub20":
        return 20, no_update, no_update, no_update
    if preset == "sub21":
        return 21, no_update, no_update, no_update
    if preset == "top_leagues":
        return no_update, no_update, no_update, ["top"]
    if preset == "under_10m":
        return no_update, no_update, ["<10M"], no_update
    if preset == "hidden_gems":
        return 21, 900, ["<10M", "10M - 20M"], []
    if preset == "min_1500":
        return no_update, 1500, no_update, no_update
    if preset == "min_2000":
        return no_update, 2000, no_update, no_update

    return no_update, no_update, no_update, no_update


# =========================
# Callback: principal
# =========================
@callback(
    Output(ID_LEAGUE, "value"),
    Output(ID_METRIC, "value"),
    Output(ID_SUMMARY, "children"),
    Output(ID_HIDDEN_GEMS, "children"),
    Output(ID_RESULTS, "children"),
    Input(ID_AGE_MAX, "value"),
    Input(ID_MIN_MIN, "value"),
    Input(ID_POS, "value"),
    Input(ID_TOP_LEAGUES, "value"),
    Input(ID_LEAGUE, "value"),
    Input(ID_COUNTRY, "value"),
    Input(ID_MARKET_VALUE, "value"),
    Input(ID_ANALYSIS_MODE, "value"),
    Input(ID_METRIC, "value"),
    Input(ID_TOPN, "value"),
    Input(ID_VIEW_MODE, "value"),
    Input(ID_MANUAL_FILTERS_STORE, "data"),
)
def update_jp_page(age_max, min_min, pos_codes, top_leagues_value, leagues, countries, market_values, analysis_mode, metric, topn, view_mode, manual_filters):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    available_leagues = {opt["value"] for opt in league_options}
    top_available = [lg for lg in TOP_LEAGUES if lg in available_leagues]

    if triggered_id == ID_TOP_LEAGUES:
        leagues_value = top_available if top_leagues_value and "top" in top_leagues_value else None
    else:
        if top_leagues_value and "top" in top_leagues_value:
            current_leagues = leagues or []
            leagues_value = current_leagues if current_leagues else top_available
        else:
            leagues_value = leagues

    metric_value = metric
    if triggered_id == ID_ANALYSIS_MODE and analysis_mode and analysis_mode != "custom_metric":
        metric_value = analysis_mode

    working_df = _apply_position_fit_score(df, pos_codes or [])

    if metric_value is None:
        metric_value = "rating"

    if metric_value not in working_df.columns:
        metric_value = "rating" if "rating" in working_df.columns else "scout_score"

    universe = get_filtered_universe(
        working_df,
        age_max=int(age_max or 23),
        min_minutes=int(min_min or 1000),
        positions=pos_codes or [],
        leagues=leagues_value or [],
        countries=countries or [],
        market_value_ranges=market_values or [],
        manual_filters=manual_filters or [],
    )

    if universe.empty:
        return (
            leagues_value,
            metric_value,
            html.Div(),
            dbc.Alert("Sem joias escondidas no recorte.", color="light"),
            dbc.Alert("Sem jogadores para esses filtros.", color="warning"),
        )

    if metric_value not in universe.columns:
        universe[metric_value] = np.nan

    ranked = universe.dropna(subset=[metric_value]).sort_values(metric_value, ascending=False).head(int(topn or 12)).copy()
    hidden_gems = get_hidden_gems(universe, metric_value)

    active_filters = []
    op_map = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "ge": ">=",
        "lt": "<",
        "le": "<=",
        "contains": "contém",
        "not_contains": "não contém",
        "startswith": "começa com",
        "endswith": "termina com",
        "is_empty": "é vazio",
        "not_empty": "não é vazio",
    }

    for f in (manual_filters or []):
        col = f.get("col")
        op = f.get("op")
        val = f.get("val", "")
        if col and op:
            if op in {"is_empty", "not_empty"}:
                active_filters.append(f"{col} {op_map.get(op, op)}")
            else:
                active_filters.append(f"{col} {op_map.get(op, op)} {val}")

    dynamic_filter_txt = "Sem filtro manual ativo." if not active_filters else " | ".join(active_filters[:2])
    if len(active_filters) > 2:
        dynamic_filter_txt += f" (+{len(active_filters) - 2})"

    summary = dbc.Row(
        [
            _summary_kpi("Jogadores no recorte", fmt_num(len(universe)), "Universo filtrado"),
            _summary_kpi(
                "Idade média",
                fmt_avg(pd.to_numeric(universe["age"], errors="coerce").mean()) if "age" in universe.columns else "NA",
                "Recorte atual",
            ),
            _summary_kpi(
                "Minutos médios",
                fmt_avg(pd.to_numeric(universe["minutesplayed"], errors="coerce").mean()) if "minutesplayed" in universe.columns else "NA",
                "Volume competitivo",
            ),
            _summary_kpi(
                f"Média {metric_value}",
                fmt_avg(pd.to_numeric(universe[metric_value], errors="coerce").mean()) if metric_value in universe.columns else "NA",
                "Métrica ativa",
            ),
            _summary_kpi(
                "Top ligas",
                fmt_num(int(universe["is_top_league"].fillna(False).sum())) if "is_top_league" in universe.columns else "0",
                "Qtd no recorte",
            ),
            _summary_kpi(
                "Até 10M",
                fmt_num(int((universe["market_value_bucket"] == "<10M").sum())) if "market_value_bucket" in universe.columns else "0",
                dynamic_filter_txt,
            ),
        ],
        className="g-3",
    )

    if hidden_gems.empty:
        hidden_gems_block = dbc.Accordion(
            [
                dbc.AccordionItem(
                    title="Joias escondidas",
                    children=[
                        dbc.Alert("Nenhum nome forte dentro da lógica de joia escondida no recorte atual.", color="light", class_name="mb-0")
                    ],
                )
            ],
            start_collapsed=True,
            flush=False,
            className="mb-0",
        )
    else:
        gem_cards = []
        for _, rg in hidden_gems.iterrows():
            pid = rg.get("playerid", None)
            player_href = ""
            try:
                if pid is not None and str(pid).strip() != "":
                    pid_int = int(float(pid))
                    player_href = f"/jogador/{pid_int}"
            except Exception:
                player_href = ""

            raw_img = (rg.get("photo_url", "") or "").strip()
            img = _fix_image_url(raw_img, pid)

            rating_txt = fmt_num(rg.get("rating", np.nan))
            goals_txt = fmt_num(rg.get("goals", np.nan))
            assists_txt = fmt_num(rg.get("assists", np.nan))

            gem_cards.append(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            html.Img(
                                                src=img,
                                                style={
                                                    "width": "64px",
                                                    "height": "64px",
                                                    "borderRadius": "14px",
                                                    "objectFit": "cover",
                                                    "backgroundColor": "rgba(0,0,0,0.06)",
                                                    "border": "1px solid rgba(108,117,125,0.12)",
                                                },
                                                alt=str(rg.get("playername", "")),
                                                referrerPolicy="no-referrer",
                                                crossOrigin="anonymous",
                                            ) if img else _empty_cover(),
                                            width="auto",
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    html.A(
                                                        str(rg.get("playername", "")),
                                                        href=player_href,
                                                        target="_blank",
                                                        className="fw-semibold text-decoration-none",
                                                        style={"color": "#6f42c1"},
                                                    ) if player_href else html.Span(str(rg.get("playername", "")), className="fw-semibold")
                                                ),
                                                html.Div(str(rg.get("teamname", "")), className="text-muted small"),
                                                html.Div(
                                                    [
                                                        html.Span(str(rg.get("leaguename", "")), style=_league_badge_style(bool(rg.get("is_top_league", False)))),
                                                        html.Span(
                                                            str(rg.get("market_value_bucket", "NA")),
                                                            style={**_market_value_badge_style(str(rg.get("market_value_bucket", "NA"))), "marginLeft": "6px"},
                                                        ),
                                                    ],
                                                    className="mt-2",
                                                ),
                                            ]
                                        ),
                                    ],
                                    className="g-2 align-items-center",
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(_quick_stat_chip("Rating", rating_txt), xs=4),
                                        dbc.Col(_quick_stat_chip("Gols", goals_txt), xs=4),
                                        dbc.Col(_quick_stat_chip("Assists", assists_txt), xs=4),
                                    ],
                                    className="g-2 mt-2",
                                ),
                                html.Div(
                                    html.A(
                                        "Ir para a página do jogador",
                                        href=player_href,
                                        target="_blank",
                                        className="small text-decoration-none d-inline-block mt-3",
                                        style={"color": "#0d6efd", "fontWeight": "600"},
                                    ) if player_href else html.Div(),
                                ),
                            ]
                        ),
                        className="border-0 h-100",
                        style={
                            "borderRadius": "20px",
                            "background": "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.98))",
                            "boxShadow": "0 10px 24px rgba(16,24,40,0.06)",
                        },
                    ),
                    xl=3,
                    lg=6,
                    md=6,
                    sm=12,
                )
            )

        hidden_gems_block = dbc.Accordion(
            [
                dbc.AccordionItem(
                    title="Joias escondidas",
                    children=[
                        html.Div(
                            "Nomes fora das top ligas, com custo mais acessível e bom recorte de produção.",
                            className="text-muted small mb-3",
                        ),
                        dbc.Row(gem_cards, className="g-3"),
                    ],
                )
            ],
            start_collapsed=True,
            flush=False,
            className="mb-0",
        )

    if ranked.empty:
        return leagues_value, metric_value, summary, hidden_gems_block, dbc.Alert("Sem jogadores para esses filtros.", color="warning")

    if view_mode == "table":
        table_df = ranked.copy()
        keep_cols = [
            c for c in [
                "playername", "teamname", "leaguename", "country", "positions_list", "age", "minutesplayed",
                "market_value_bucket", "rating", "goals", "assists", "xg", "xa",
                "scout_score", "elite_now_score", "upside_score",
                "value_opportunity_score", "offensive_score", "position_fit_score"
            ] if c in table_df.columns
        ]
        table_df = table_df[keep_cols].copy()

        if "positions_list" in table_df.columns:
            table_df["positions_list"] = table_df["positions_list"].apply(
                lambda x: " | ".join([str(v) for v in x[:3]]) if isinstance(x, list) else str(x)
            )

        nice_names = {
            "playername": "Jogador",
            "teamname": "Time",
            "leaguename": "Liga",
            "country": "País",
            "positions_list": "Posições",
            "age": "Idade",
            "minutesplayed": "Minutos",
            "market_value_bucket": "Market Value",
            "rating": "Rating",
            "goals": "Gols",
            "assists": "Assists",
            "xg": "xG",
            "xa": "xA",
            "scout_score": "Scout Score",
            "elite_now_score": "Elite Now",
            "upside_score": "Upside",
            "value_opportunity_score": "Value Opp.",
            "offensive_score": "Offensive",
            "position_fit_score": "Fit Posição",
        }
        table_df = table_df.rename(columns=nice_names)

        for c in table_df.columns:
            if c not in {"Jogador", "Time", "Liga", "País", "Posições", "Market Value"}:
                table_df[c] = pd.to_numeric(table_df[c], errors="coerce")

        results = dbc.Card(
            className="border-0",
            style={"borderRadius": "24px", "boxShadow": "0 12px 28px rgba(16,24,40,0.08)"},
            children=[
                dbc.CardBody(
                    [
                        html.Div("Tabela comparativa", className="fw-bold mb-3", style={"fontSize": "18px"}),
                        dash_table.DataTable(
                            columns=[
                                {
                                    "name": c,
                                    "id": c,
                                    "type": "numeric" if c not in {"Jogador", "Time", "Liga", "País", "Posições", "Market Value"} else "text",
                                }
                                for c in table_df.columns
                            ],
                            data=table_df.to_dict("records"),
                            sort_action="native",
                            filter_action="none",
                            page_action="none",
                            style_table={"overflowX": "auto"},
                            style_header={
                                "backgroundColor": "#f8fafc",
                                "fontWeight": "700",
                                "border": "none",
                                "padding": "10px",
                            },
                            style_cell={
                                "padding": "10px",
                                "fontSize": "13px",
                                "border": "none",
                                "textAlign": "left",
                                "backgroundColor": "white",
                                "minWidth": "110px",
                                "width": "110px",
                                "maxWidth": "220px",
                            },
                            style_data_conditional=[
                                {"if": {"row_index": "odd"}, "backgroundColor": "#fbfdff"},
                            ],
                        ),
                    ]
                )
            ],
        )
        return leagues_value, metric_value, summary, hidden_gems_block, results

    cards = []
    for idx, (_, r) in enumerate(ranked.iterrows(), start=1):
        pid = r.get("playerid", None)
        pid_int = None
        try:
            pid_int = int(float(pid))
        except Exception:
            pid_int = None

        val_txt = fmt_num(r.get(metric_value, np.nan))
        age_txt = fmt_num(r.get("age", np.nan))
        min_txt = fmt_num(r.get("minutesplayed", np.nan))
        mv_bucket_txt = str(r.get("market_value_bucket", "NA")).strip() or "NA"

        raw_img = (r.get("photo_url", "") or "").strip()
        img = _fix_image_url(raw_img, pid)

        player_name = str(r.get("playername", "") or "")
        team_name = str(r.get("teamname", "") or "")
        league_txt = str(r.get("leaguename", "")).strip() if "leaguename" in r.index else ""
        country_txt = str(r.get("country", "")).strip() if "country" in r.index else ""
        positions_txt = _positions_text(r)
        is_top_league = league_txt in TOP_LEAGUES
        insight_txt = _player_insight(r)
        context_badges = _build_context_badges(r)

        img_style = {
            "width": "78px",
            "height": "78px",
            "borderRadius": "16px",
            "objectFit": "cover",
            "backgroundColor": "rgba(0,0,0,0.06)",
            "border": "1px solid rgba(108,117,125,0.12)",
            "boxShadow": "0 4px 14px rgba(16,24,40,0.08)",
        }

        player_href = ""
        try:
            if pid_int is not None:
                player_href = f"/jogador/{pid_int}"
        except Exception:
            player_href = ""

        quick_items = []

        if "rating" in r.index:
            rv = _safe_float_from_row(r, "rating")
            quick_items.append(("Rating", fmt_num(rv) if rv is not None else "NA"))

        if "goals" in r.index:
            gv = _safe_int_from_row(r, "goals")
            quick_items.append(("Gols", str(gv) if gv is not None else "NA"))

        if "assists" in r.index:
            av = _safe_int_from_row(r, "assists")
            quick_items.append(("Assists", str(av) if av is not None else "NA"))

        if "appearances" in r.index:
            ap = _safe_int_from_row(r, "appearances")
            quick_items.append(("Jogos", str(ap) if ap is not None else "NA"))

        if "xg" in r.index:
            xg = _safe_float_from_row(r, "xg")
            quick_items.append(("xG", fmt_num(xg) if xg is not None else "NA"))

        if "xa" in r.index:
            xa = _safe_float_from_row(r, "xa")
            quick_items.append(("xA", fmt_num(xa) if xa is not None else "NA"))

        quick_items = quick_items[:6]
        quick_row = dbc.Row([_quick_stat_chip(lbl, val) for lbl, val in quick_items], className="g-2 mt-3") if quick_items else None

        cards.append(
            dbc.Col(
                dbc.Card(
                    className="h-100 border-0",
                    style={
                        "borderRadius": "24px",
                        "overflow": "hidden",
                        "background": "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.98))",
                        "boxShadow": _card_shadow(idx),
                        "transition": "transform 0.18s ease, box-shadow 0.18s ease",
                    },
                    children=[
                        html.Div(
                            style={
                                "height": "6px",
                                "background": "linear-gradient(90deg, #6f42c1, #0d6efd)",
                            }
                        ),
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Div(_ranking_badge(idx), style={"marginBottom": "8px"}),
                                                html.Div(
                                                    html.Img(
                                                        src=img,
                                                        style=img_style,
                                                        alt=player_name,
                                                        referrerPolicy="no-referrer",
                                                        crossOrigin="anonymous",
                                                    ) if img else _empty_cover()
                                                ),
                                            ],
                                            width="auto",
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    [
                                                        html.Div(player_name, className="fw-bold", style={"fontSize": "18px", "lineHeight": "20px"}),
                                                        html.Div(team_name, className="text-muted", style={"fontSize": "13px", "marginTop": "4px"}),
                                                        html.Div(positions_txt, className="text-muted", style={"fontSize": "12px", "marginTop": "4px"}) if positions_txt else html.Div(),
                                                    ]
                                                ),
                                                html.Div(
                                                    [
                                                        html.Span(league_txt or "Sem liga", style=_league_badge_style(is_top_league)),
                                                        html.Span(
                                                            country_txt or "Sem país",
                                                            style={
                                                                "fontSize": "11px",
                                                                "padding": "4px 10px",
                                                                "borderRadius": "999px",
                                                                "display": "inline-block",
                                                                "fontWeight": "600",
                                                                "background": "rgba(32,201,151,0.10)",
                                                                "color": "#0f8c6b",
                                                                "border": "1px solid rgba(15,140,107,0.18)",
                                                                "marginLeft": "6px",
                                                                "marginTop": "6px",
                                                            },
                                                        ),
                                                    ],
                                                    style={"marginTop": "10px"},
                                                ),
                                            ]
                                        ),
                                    ],
                                    className="g-3 align-items-start",
                                ),

                                html.Div(context_badges, style={"marginTop": "14px"}),

                                html.Div(
                                    [
                                        html.Div(
                                            "Insight rápido",
                                            className="text-muted",
                                            style={"fontSize": "11px", "textTransform": "uppercase", "letterSpacing": "0.5px"},
                                        ),
                                        html.Div(
                                            insight_txt,
                                            style={"fontSize": "13px", "lineHeight": "18px", "marginTop": "6px", "color": "#495057"},
                                        ),
                                    ],
                                    style={
                                        "marginTop": "10px",
                                        "padding": "12px 14px",
                                        "borderRadius": "16px",
                                        "background": "rgba(111,66,193,0.05)",
                                        "border": "1px solid rgba(111,66,193,0.10)",
                                    },
                                ),

                                html.Div(
                                    [
                                        html.Div(
                                            "Valor de mercado",
                                            className="text-muted",
                                            style={"fontSize": "11px", "textTransform": "uppercase", "letterSpacing": "0.5px"},
                                        ),
                                        html.Div(
                                            mv_bucket_txt,
                                            style={**_market_value_badge_style(mv_bucket_txt), "marginTop": "6px"},
                                        ),
                                    ],
                                    style={
                                        "marginTop": "16px",
                                        "padding": "12px 14px",
                                        "borderRadius": "16px",
                                        "background": "rgba(248,249,250,0.9)",
                                        "border": "1px solid rgba(108,117,125,0.10)",
                                    },
                                ),

                                quick_row if quick_row else html.Div(),

                                html.Div(
                                    [
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    [
                                                        html.Div("Idade", className="text-muted", style={"fontSize": "11px", "textTransform": "uppercase"}),
                                                        html.Div(age_txt, className="fw-bold", style={"fontSize": "16px"}),
                                                    ],
                                                    xs=4,
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Div("Minutos", className="text-muted", style={"fontSize": "11px", "textTransform": "uppercase"}),
                                                        html.Div(min_txt, className="fw-bold", style={"fontSize": "16px"}),
                                                    ],
                                                    xs=4,
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Div("Métrica", className="text-muted", style={"fontSize": "11px", "textTransform": "uppercase"}),
                                                        html.Div(val_txt, className="fw-bold", style={"fontSize": "16px", "color": "#6f42c1"}),
                                                    ],
                                                    xs=4,
                                                ),
                                            ],
                                            className="g-2",
                                        )
                                    ],
                                    style={
                                        "marginTop": "16px",
                                        "padding": "14px",
                                        "borderRadius": "18px",
                                        "background": "linear-gradient(180deg, rgba(111,66,193,0.06), rgba(13,110,253,0.04))",
                                        "border": "1px solid rgba(111,66,193,0.10)",
                                    },
                                ),

                                html.Div(
                                    [
                                        html.Div(
                                            f"Ranking por {metric_value}",
                                            className="fw-semibold",
                                            style={"fontSize": "12px", "color": "#495057"},
                                        ),
                                        html.Div(
                                            val_txt,
                                            style={
                                                "fontSize": "22px",
                                                "fontWeight": "800",
                                                "lineHeight": "24px",
                                                "marginTop": "4px",
                                                "color": "#212529",
                                            },
                                        ),
                                    ],
                                    style={"marginTop": "16px"},
                                ),

                                html.Hr(style={"margin": "18px 0 14px 0", "opacity": "0.10"}),

                                dbc.Button(
                                    "Add to comparison",
                                    id={"type": COMPARE_BTN_TYPE, "index": pid_int if pid_int is not None else f"na_{idx}"},
                                    color="light",
                                    className="w-100 mb-2",
                                    n_clicks=0,
                                    style={"borderRadius": "12px", "fontWeight": "600"},
                                ),

                                html.Div(
                                    [
                                        html.A(
                                            "Ir para a página do jogador",
                                            href=player_href,
                                            target="_blank",
                                            className="small fw-semibold text-decoration-none d-block mb-2",
                                            style={"color": "#6f42c1"},
                                        ) if player_href else html.Div("", className="small mb-2"),
                                        html.A(
                                            "Abrir no SofaScore",
                                            href=r.get("sofascore_url", ""),
                                            target="_blank",
                                            className="small fw-semibold text-decoration-none d-block",
                                            style={"color": "#0d6efd"},
                                        ) if r.get("sofascore_url", "") else html.Div("", className="small"),
                                    ]
                                ),
                            ],
                            style={"padding": "18px"},
                        ),
                    ],
                ),
                xl=3,
                lg=4,
                md=6,
                sm=12,
            )
        )

    return leagues_value, metric_value, summary, hidden_gems_block, dbc.Row(cards, className="g-4")


# =========================
# Callback: add/remove comparison / limpar
# =========================
@callback(
    Output(ID_COMPARISON_STORE, "data"),
    Input({"type": COMPARE_BTN_TYPE, "index": ALL}, "n_clicks"),
    Input({"type": REMOVE_COMPARE_BTN_TYPE, "index": ALL}, "n_clicks"),
    Input(ID_CLEAR_COMPARISON, "n_clicks"),
    State(ID_COMPARISON_STORE, "data"),
    prevent_initial_call=True,
)
def update_comparison_store(add_clicks, remove_clicks, clear_clicks, comparison_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update

    triggered = ctx.triggered[0]
    prop_id = triggered["prop_id"].split(".")[0]
    prop_value = triggered.get("value", None)

    if prop_id == ID_CLEAR_COMPARISON:
        if not prop_value:
            return no_update
        return []

    try:
        payload = json.loads(prop_id)
        action_type = payload.get("type")
        pid = payload.get("index")
    except Exception:
        return no_update

    if pid is None or (isinstance(pid, str) and str(pid).startswith("na_")):
        return no_update

    if prop_value in (None, 0):
        return no_update

    current = comparison_data or []

    if action_type == REMOVE_COMPARE_BTN_TYPE:
        return [item for item in current if int(item.get("playerid")) != int(pid)]

    if action_type != COMPARE_BTN_TYPE:
        return no_update

    current_ids = {int(item["playerid"]) for item in current if "playerid" in item}
    if int(pid) in current_ids:
        return no_update

    if len(current) >= 4:
        return no_update

    if "playerid" not in df.columns:
        return no_update

    playerid_series = pd.to_numeric(df["playerid"], errors="coerce")
    player_row = df[playerid_series == int(pid)]

    if player_row.empty:
        return no_update

    r = player_row.iloc[0]

    current.append(
        {
            "playerid": int(pid),
            "playername": str(r.get("playername", "")),
            "teamname": str(r.get("teamname", "")),
        }
    )

    return current


# =========================
# Callback: render comparison area
# =========================
@callback(
    Output(ID_COMPARISON_DISPLAY, "children"),
    Input(ID_COMPARISON_STORE, "data"),
)
def render_comparison_area(comparison_data):
    comparison_data = comparison_data or []

    if not comparison_data:
        return dbc.Alert(
            "Nenhum jogador adicionado ainda. Use o botão Add to comparison nos cards.",
            color="light",
            class_name="mb-0"
        )

    chips = []
    ids = []

    for item in comparison_data:
        pid = item.get("playerid")
        if pid is None:
            continue

        ids.append(str(pid))
        chips.append(
            html.Div(
                [
                    dbc.Button(
                        "×",
                        id={"type": REMOVE_COMPARE_BTN_TYPE, "index": int(pid)},
                        color="link",
                        n_clicks=0,
                        style={
                            "position": "absolute",
                            "top": "-2px",
                            "right": "4px",
                            "padding": "0",
                            "lineHeight": "12px",
                            "fontSize": "16px",
                            "color": "#6f42c1",
                            "textDecoration": "none",
                            "fontWeight": "700",
                        },
                    ),
                    html.Div(
                        f"{item.get('playername', '')}",
                        style={"fontWeight": "700", "fontSize": "12px", "paddingRight": "14px"},
                    ),
                    html.Div(
                        f"{item.get('teamname', '')}",
                        style={"fontSize": "11px", "opacity": "0.85", "marginTop": "2px"},
                    ),
                ],
                style={
                    "position": "relative",
                    "display": "inline-block",
                    "padding": "10px 26px 10px 12px",
                    "borderRadius": "14px",
                    "background": "rgba(111,66,193,0.10)",
                    "color": "#6f42c1",
                    "marginRight": "8px",
                    "marginBottom": "8px",
                    "border": "1px solid rgba(111,66,193,0.16)",
                    "minWidth": "170px",
                },
            )
        )

    compare_url = ""
    if ids:
        compare_url = "https://www.sofascore.com/pt/football/player/compare?ids=" + ",".join(ids)

    return html.Div(
        [
            html.Div(
                "Jogadores adicionados para comparação externa no SofaScore.",
                className="text-muted small mb-2"
            ),
            html.Div(chips, className="mb-3"),
            html.A(
                "Comparison",
                href=compare_url,
                target="_blank",
                className="btn btn-primary",
                style={"borderRadius": "12px", "fontWeight": "600"},
            ) if compare_url else html.Div(),
        ]
    )