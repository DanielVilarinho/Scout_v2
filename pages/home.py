import numpy as np
import pandas as pd

import dash
from dash import dcc, html, dash_table, Input, Output, State, no_update, callback_context
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

from data import DF, POS_PT, POSITION_ORDER, pos_to_pt

dash.register_page(__name__, path="/", name="Dashboard", order=0)

df = DF  # mantém seu nome original


# =========================
# 3) AXIS OPTIONS
# =========================
numeric_cols = df.select_dtypes(include="number").columns.tolist()
drop_numeric_like_ids = {"playerid", "teamid", "tournamentid", "seasonid", "dateofbirthtimestamp"}
axis_options = [c for c in numeric_cols if c not in drop_numeric_like_ids]

for extra in ["goals_per90", "assists_per90", "ga_per90", "value_performance"]:
    if extra in df.columns and extra not in axis_options:
        axis_options.append(extra)

# ✅ ALTERAÇÃO (3): adiciona coluna Perfil (link p/ página do jogador)
IMPORTANT_COLS = [
    "perfil",  # <- nova
    "playername",
    "age",
    "teamname",
    "leaguename",
    "country",
    "positionsdetailed",
    "minutesplayed",
    "rating",
    "goals",
    "assists",
    "appearances",
    "proposedmarketvalue",
    "goals_per90" if "goals_per90" in df.columns else None,
    "assists_per90" if "assists_per90" in df.columns else None,
    "ga_per90" if "ga_per90" in df.columns else None,
    "value_performance" if "value_performance" in df.columns else None,
    "sofascore",
]
IMPORTANT_COLS = [c for c in IMPORTANT_COLS if c and c in (["perfil"] + df.columns.tolist())]


# =========================
# 4) HELPERS
# =========================
AGE_BANDS = {
    "U-20": lambda s: s < 20,
    "U-23": lambda s: s <= 23,
    "U-27": lambda s: s <= 27,
    "U–30": lambda s: s <= 30,
    "31+":      lambda s: s >= 31,
}
MIN_BANDS = {
    "<300":    lambda s: s < 300,
    ">600":    lambda s: s >= 600,
    ">1000":   lambda s: s >= 1000,
}

def human_money(x: float) -> str:
    if x is None or np.isnan(x):
        return "NA"
    x = float(x)
    ax = abs(x)
    if ax >= 1_000_000_000:
        return f"{x/1_000_000_000:.1f}B"
    if ax >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    if ax >= 1_000:
        return f"{x/1_000:.1f}K"
    return f"{x:.0f}"

def safe_percentile(s: pd.Series, p: float):
    s2 = s.replace([np.inf, -np.inf], np.nan).dropna()
    if s2.empty:
        return np.nan
    return float(np.nanpercentile(s2, p))

def zscore(s: pd.Series):
    s2 = s.replace([np.inf, -np.inf], np.nan).astype(float)
    mu = np.nanmean(s2)
    sd = np.nanstd(s2)
    if sd == 0 or np.isnan(sd):
        return pd.Series(np.zeros(len(s2)), index=s.index)
    return (s2 - mu) / sd


# =========================
# 5) DISCRETE BANDS (Market Value + Rating min)
# =========================
MV_BANDS_MAP = {"ALL": None}
MV_OPTIONS = [{"label": "Todos", "value": "ALL"}]

if "proposedmarketvalue" in df.columns and df["proposedmarketvalue"].notna().any():
    q = df["proposedmarketvalue"].replace([np.inf, -np.inf], np.nan).dropna()
    q0  = float(np.nanmin(q))
    q25 = float(np.nanpercentile(q, 25))
    q50 = float(np.nanpercentile(q, 50))
    q75 = float(np.nanpercentile(q, 75))
    q90 = float(np.nanpercentile(q, 90))
    q95 = float(np.nanpercentile(q, 95)) if len(q) >= 20 else q90
    q100= float(np.nanmax(q))

    bands_pct = [
        ("MV_P25",  f"Baixo (até P25)  ≤ {human_money(q25)}", (q0, q25)),
        ("MV_P50",  f"Médio-baixo (P25–P50)  {human_money(q25)}–{human_money(q50)}", (q25, q50)),
        ("MV_P75",  f"Médio (P50–P75)  {human_money(q50)}–{human_money(q75)}", (q50, q75)),
        ("MV_P90",  f"Alto (P75–P90)  {human_money(q75)}–{human_money(q90)}", (q75, q90)),
        ("MV_P95",  f"Muito alto (P90–P95)  {human_money(q90)}–{human_money(q95)}", (q90, q95)),
        ("MV_P95P", f"Elite (P95+)  ≥ {human_money(q95)}", (q95, q100)),
    ]

    abs_bands = []
    if q100 >= 4_500_000:
        abs_bands = [
            ("MV_4_5_10",  "≥ 4.5M e < 10M",   (4_500_000, min(9_999_999, q100))),
            ("MV_10_20",   "≥ 10M e < 20M",    (10_000_000, min(19_999_999, q100))),
            ("MV_20_50",   "≥ 20M e < 50M",    (20_000_000, min(49_999_999, q100))),
            ("MV_50_PLUS", "≥ 50M",            (50_000_000, q100)),
        ]
        abs_bands = [(k, lbl, rng) for (k, lbl, rng) in abs_bands if rng[0] <= rng[1]]

    for k, lbl, rng in bands_pct:
        MV_BANDS_MAP[k] = rng
        MV_OPTIONS.append({"label": lbl, "value": k})

    if abs_bands:
        MV_OPTIONS.append({"label": "────────  Faixas absolutas (acima de 4.5M)  ────────", "value": "SEP_ABS", "disabled": True})
        for k, lbl, rng in abs_bands:
            MV_BANDS_MAP[k] = rng
            lo, hi = rng
            if k == "MV_50_PLUS":
                MV_OPTIONS.append({"label": f"{lbl} (até {human_money(hi)})", "value": k})
            else:
                MV_OPTIONS.append({"label": f"{lbl} (até {human_money(hi)})", "value": k})

RATING_MIN_MAP = {"NONE": None}
RATING_OPTIONS = [{"label": "Sem mínimo", "value": "NONE"}]

if "rating" in df.columns and df["rating"].notna().any():
    rmin = float(np.nanmin(df["rating"]))
    rmax = float(np.nanmax(df["rating"]))
    candidates = [6.5, 6.8, 7.0, 7.2, 7.4, 7.6, 7.8]
    thresholds = [t for t in candidates if t >= rmin and t <= rmax]
    thresholds = sorted(set(thresholds))
    for t in thresholds:
        key = f"R_{str(t).replace('.','_')}"
        RATING_MIN_MAP[key] = float(t)
        RATING_OPTIONS.append({"label": f"≥ {t:.2f}", "value": key})


# =========================
# 6) POSITION PRESETS -> METRICS
# =========================
def _only_existing(candidates, available):
    out = [c for c in candidates if c in available]
    seen = set()
    out2 = []
    for x in out:
        if x not in seen:
            out2.append(x)
            seen.add(x)
    return out2

# ✅ ALTERAÇÃO (1): presets priorizando métricas *_per90
ROLE_PRESETS = {
    "GK": ["rating", "saves", "savepercentage", "cleansheets", "goalsconceded"],

    "DC": [
        "rating",
        "defensive_actions_per90",
        "tackles_per90",
        "interceptions_per90",
        "aerialduelswon_per90",
        "errorleadtogoal_per90",
        "accuratepasses_per90",
    ],

    "DL": [
        "rating",
        "keypasses_per90",
        "expectedassists_per90",
        "assists_per90",
        "successfuldribbles_per90",
        "tackles_per90",
        "interceptions_per90",
        "accuratepasses_per90",
    ],
    "DR": [
        "rating",
        "keypasses_per90",
        "expectedassists_per90",
        "assists_per90",
        "successfuldribbles_per90",
        "tackles_per90",
        "interceptions_per90",
        "accuratepasses_per90",
    ],

    "DM": [
        "rating",
        "defensive_actions_per90",
        "tackles_per90",
        "interceptions_per90",
        "aerialduelswon_per90",
        "accuratepasses_per90",
        "totalpasses_per90",
    ],

    "MC": [
        "rating",
        "keypasses_per90",
        "expectedassists_per90",
        "assists_per90",
        "goals_per90",
        "expectedgoals_per90",
        "tackles_per90",
        "interceptions_per90",
    ],

    "AM": [
        "rating",
        "keypasses_per90",
        "expectedassists_per90",
        "assists_per90",
        "goals_per90",
        "expectedgoals_per90",
        "totalshots_per90",
        "shotsontarget_per90",
    ],

    "LW": [
        "rating",
        "successfuldribbles_per90",
        "keypasses_per90",
        "expectedassists_per90",
        "assists_per90",
        "goals_per90",
        "expectedgoals_per90",
        "shotsontarget_per90",
    ],
    "RW": [
        "rating",
        "successfuldribbles_per90",
        "keypasses_per90",
        "expectedassists_per90",
        "assists_per90",
        "goals_per90",
        "expectedgoals_per90",
        "shotsontarget_per90",
    ],

    "ST": [
        "rating",
        "goals_per90",
        "expectedgoals_per90",
        "shotsontarget_per90",
        "totalshots_per90",
        "assists_per90",
        "expectedassists_per90",
        "aerialduelswon_per90",
    ],
}

DEFAULT_PRESET = _only_existing(
    [
        "rating",
        "minutesplayed",
        "goals_per90",
        "assists_per90",
        "expected_goal_contribution_per90",
        "expectedgoals_per90",
        "expectedassists_per90",
        "value_performance",
        "ga_per90",
    ],
    axis_options
)

def preset_metrics_for_pos(pos_code: str, max_len: int = 7):
    if not pos_code:
        return DEFAULT_PRESET[:max_len]
    code = str(pos_code).upper().strip()

    if code in ["LCB", "RCB"]:
        code = "CB"
    if code in ["LWB"]:
        code = "LB"
    if code in ["RWB"]:
        code = "RB"
    if code in ["CDM"]:
        code = "DM"
    if code in ["CAM", "LAM", "RAM"]:
        code = "AM"
    if code in ["LM", "RM"]:
        code = "AM"
    if code in ["CF", "SS", "RF", "LF", "FW"]:
        code = "ST"

    cand = ROLE_PRESETS.get(code, DEFAULT_PRESET)
    picked = _only_existing(cand, axis_options)

    if len(picked) < 3:
        picked = (picked + DEFAULT_PRESET)[:max_len]
    return picked[:max_len]


# =========================
# 6.5) SMART FILTER: TOP 12 LIGAS (EXATO)
# =========================
TOP12_LEAGUES_EXPLICIT = [
    "Brasileirão Betano",
    "Campeonato Brasileiro Série A",
    "Campeonato Brasileiro (Série A)",
    "Liga Profesional de Fútbol - Apertura",
    "Liga Profesional de Fútbol - Clausura",
    "Liga Profesional de Fútbol - Finalización",
    "Primera División Argentina - Apertura",
    "Primera División Argentina - Clausura",
    "Primera División Argentina - Finalización",
    "Liga Profesional Argentina - Apertura",
    "Liga Profesional Argentina - Clausura",
    "Liga Profesional Argentina - Finalización",
    "Liga Argentina - Apertura",
    "Liga Argentina - Clausura",
    "Liga Argentina - Finalización",
    "Copa de la Liga Profesional",
    "Liga MX - Apertura",
    "Liga MX - Clausura",
    "Primera División de México - Apertura",
    "Primera División de México - Clausura",
    "Liga México - Apertura",
    "Liga México - Clausura",
    "Major League Soccer",
    "MLS",
    "Premier League",
    "LaLiga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Primeira Liga",
    "Eredivisie",
    "Belgian Pro League",
]
TOP12_LEAGUES_SET = set(TOP12_LEAGUES_EXPLICIT)


# =========================
# 7) FILTER LOGIC
# =========================
def _positions_match(lst, sel_upper: set[str]) -> bool:
    if lst is None or (isinstance(lst, float) and np.isnan(lst)):
        return False

    if isinstance(lst, (list, tuple, set)):
        items = lst
    elif isinstance(lst, str):
        items = [x.strip() for x in lst.split(",")]
    else:
        return False

    for p in items:
        if p is None:
            continue
        if str(p).upper().strip() in sel_upper:
            return True
    return False

def apply_filters(
    base: pd.DataFrame,
    age_band: str | None,
    min_band: str | None,
    leagues: list[str] | None,
    positions: list[str] | None,
    countries: list[str] | None,
    mv_band_key: str | None,
    rating_min_key: str | None,
    smart_filters: list[str] | None,
    young_age_max: int,
    young_min_min: int,
    vet_age_min: int,
    vet_ga_min: float,
    cb_pct: int,
    outlier_z: float
) -> pd.DataFrame:
    out = base

    if age_band and age_band in AGE_BANDS and "age" in out.columns:
        out = out[AGE_BANDS[age_band](out["age"])]

    if min_band and min_band in MIN_BANDS and "minutesplayed" in out.columns:
        out = out[MIN_BANDS[min_band](out["minutesplayed"])]

    if leagues and "leaguename" in out.columns:
        out = out[out["leaguename"].isin(leagues)]

    if positions and "positions_list" in out.columns:
        sel = set([str(p).upper().strip() for p in positions if p])
        if sel:
            out = out[out["positions_list"].apply(lambda lst: _positions_match(lst, sel))]

    if countries and "country" in out.columns:
        out = out[out["country"].isin(countries)]

    if mv_band_key and mv_band_key in MV_BANDS_MAP and MV_BANDS_MAP[mv_band_key] and "proposedmarketvalue" in out.columns:
        lo, hi = MV_BANDS_MAP[mv_band_key]
        out = out[
            (out["proposedmarketvalue"].fillna(np.nan) >= float(lo)) &
            (out["proposedmarketvalue"].fillna(np.nan) <= float(hi))
        ]

    if rating_min_key and rating_min_key in RATING_MIN_MAP and RATING_MIN_MAP[rating_min_key] is not None and "rating" in out.columns:
        thr = float(RATING_MIN_MAP[rating_min_key])
        out = out[out["rating"].fillna(-np.inf) >= thr]

    smart_filters = smart_filters or []

    if "young_minutes" in smart_filters and {"age", "minutesplayed"}.issubset(out.columns):
        out = out[(out["age"] <= young_age_max) & (out["minutesplayed"] >= young_min_min)]

    if "veterans_prod" in smart_filters and {"age", "goals", "assists"}.issubset(out.columns):
        out = out[(out["age"] >= vet_age_min) & ((out["goals"].fillna(0) + out["assists"].fillna(0)) >= vet_ga_min)]

    if "cost_benefit" in smart_filters and {"rating", "proposedmarketvalue"}.issubset(out.columns):
        tmp = out.copy()
        tmp["cb"] = tmp["rating"] / tmp["proposedmarketvalue"].replace(0, np.nan)
        thr = safe_percentile(tmp["cb"], cb_pct)
        if not np.isnan(thr):
            out = tmp[tmp["cb"] >= thr].drop(columns=["cb"], errors="ignore")

    if "value_perf" in smart_filters and "value_performance" in out.columns:
        thr = safe_percentile(out["value_performance"], cb_pct)
        if not np.isnan(thr):
            out = out[out["value_performance"] >= thr]

    if "positive_outliers" in smart_filters and "rating" in out.columns:
        tmp = out.copy()
        z_r = zscore(tmp["rating"])
        if "ga_per90" in tmp.columns:
            z_ga = zscore(tmp["ga_per90"].replace([np.inf, -np.inf], np.nan))
            score = z_r + z_ga.fillna(0)
        else:
            score = z_r
        out = tmp[score >= float(outlier_z)]

    if "top12_leagues" in smart_filters and "leaguename" in out.columns:
        present = set(out["leaguename"].dropna().unique().tolist())
        allowed = sorted(list(present.intersection(TOP12_LEAGUES_SET)))
        out = out[out["leaguename"].isin(allowed)]

    return out


# =========================
# 8) UI OPTIONS
# =========================
league_options = sorted(df["leaguename"].dropna().unique().tolist()) if "leaguename" in df.columns else []
pos_codes = sorted({str(p).upper() for lst in df["positions_list"] for p in lst if p}) if "positions_list" in df.columns else []

pos_options = [{"label": POS_PT[p], "value": p} for p in POSITION_ORDER if p in POS_PT]

country_options = []
if "country" in df.columns:
    country_list = sorted([str(x) for x in df["country"].dropna().unique().tolist()])
    country_options = [{"label": c, "value": c} for c in country_list]

default_bar_metric = "rating" if "rating" in axis_options else (axis_options[0] if axis_options else None)
default_scatter_x = "minutesplayed" if "minutesplayed" in axis_options else (axis_options[0] if axis_options else None)
default_scatter_y = "rating" if "rating" in axis_options else (axis_options[min(1, len(axis_options)-1)] if axis_options else None)

players_opts = []

def order_position_codes(codes: list[str]) -> list[str]:
    codes = [str(c).upper().strip() for c in (codes or []) if c]
    unique = []
    seen = set()
    for c in codes:
        if c not in seen:
            unique.append(c)
            seen.add(c)

    ordered = [c for c in POSITION_ORDER if c in seen]
    rest = sorted([c for c in unique if c not in set(ordered)])
    return ordered + rest

preset_pos_opts = [{"label": pos_to_pt(code), "value": code} for code in order_position_codes(pos_codes)]

def make_player_options(dff: pd.DataFrame):
    if dff is None or dff.empty:
        return []
    needed = {"playername", "teamname", "_row_id"}
    if not needed.issubset(set(dff.columns)):
        return []
    tmp2 = dff[["playername", "teamname", "_row_id"]].fillna("")
    tmp2["label"] = tmp2["playername"].astype(str) + " — " + tmp2["teamname"].astype(str)
    tmp2 = tmp2.sort_values("label")
    return [{"label": r["label"], "value": int(r["_row_id"])} for _, r in tmp2.iterrows()]


# =========================
# 9.1) LAYOUT HOME
# =========================
layout = dbc.Container(
    fluid=True,
    children=[
        dcc.Store(id="selected_ids_store", storage_type="local"),

        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.H2("Player Stats Dashboard", className="mb-1"),
                        html.Div("Filtros globais aplicam em tudo. Seleção no scatter/bar filtra a tabela.", className="text-muted"),
                    ],
                    className="py-3"
                )
            )
        ),

        dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Faixa de idade", className="fw-semibold"),
                                    dcc.Dropdown(
                                        options=[{"label": k, "value": k} for k in AGE_BANDS.keys()],
                                        value=None,
                                        placeholder="Todas",
                                        clearable=True,
                                        id="age_band",
                                    ),
                                    html.Div("Filtra por faixa etária.", className="text-muted small-help"),
                                ],
                                md=2
                            ),
                            dbc.Col(
                                [
                                    html.Label("Faixa de minutos", className="fw-semibold"),
                                    dcc.Dropdown(
                                        options=[{"label": k, "value": k} for k in MIN_BANDS.keys()],
                                        value=">600",
                                        placeholder="Todos",
                                        clearable=True,
                                        id="min_band",
                                    ),
                                    html.Div("Filtra pelo total de minutos.", className="text-muted small-help"),
                                ],
                                md=2
                            ),
                            dbc.Col(
                                [
                                    html.Label("Liga", className="fw-semibold"),
                                    dcc.Dropdown(
                                        options=[{"label": x, "value": x} for x in league_options],
                                        value=None,
                                        placeholder="Todas",
                                        multi=True,
                                        id="league_filter",
                                    ),
                                    html.Div("Filtra pela liga/competição.", className="text-muted small-help"),
                                ],
                                md=3
                            ),
                            dbc.Col(
                                [
                                    html.Label("Posição", className="fw-semibold"),
                                    dcc.Dropdown(
                                        options=pos_options,
                                        value=None,
                                        placeholder="Todas",
                                        multi=True,
                                        id="pos_filter",
                                    ),
                                    html.Div("Filtra por posição (em português).", className="text-muted small-help"),
                                ],
                                md=3
                            ),
                            dbc.Col(
                                [
                                    html.Label("Nacionalidade", className="fw-semibold"),
                                    dcc.Dropdown(
                                        options=country_options,
                                        value=None,
                                        placeholder="Todas",
                                        multi=True,
                                        id="country_filter",
                                    ),
                                    html.Div("Filtra por país (campo country).", className="text-muted small-help"),
                                ],
                                md=2
                            ),
                        ],
                        className="g-3 mb-2"
                    ),

                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Market Value (faixas)", className="fw-semibold"),
                                    dcc.Dropdown(
                                        id="mv_band",
                                        options=MV_OPTIONS,
                                        value="ALL",
                                        clearable=False,
                                    ),
                                    html.Div("Faixas por percentis + faixas absolutas acima de 4.5M.", className="text-muted small-help"),
                                ],
                                md=6
                            ),
                            dbc.Col(
                                [
                                    html.Label("Rating mínimo (faixas)", className="fw-semibold"),
                                    dcc.Dropdown(
                                        id="rating_min_band",
                                        options=RATING_OPTIONS,
                                        value="NONE",
                                        clearable=False,
                                    ),
                                    html.Div("Corte mínimo de rating.", className="text-muted small-help"),
                                ],
                                md=6
                            ),
                        ],
                        className="g-3 mb-2"
                    ),

                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    "Limpar filtros",
                                    id="clear_filters",
                                    color="warning",
                                    className="me-2",
                                ),
                                md="auto"
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "Limpar seleção (scatter/bar)",
                                    id="clear_selection",
                                    color="secondary",
                                    outline=True
                                ),
                                md="auto"
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "Smart filters (expandir/retrair)",
                                    id="toggle_smart",
                                    color="primary",
                                    outline=True
                                ),
                                md="auto"
                            ),
                            dbc.Col(
                                html.Div(id="selection_info", className="text-muted"),
                                md=True
                            )
                        ],
                        className="g-2 align-items-center mt-2"
                    ),

                    dbc.Collapse(
                        id="smart_collapse",
                        is_open=False,
                        children=[
                            html.Hr(),
                            html.Div("Smart filters", className="fw-semibold mb-2"),

                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Checklist(
                                                id="smart_filters",
                                                options=[
                                                    {"label": html.Span(["Jovens com muitos minutos ", html.Span("ⓘ", id="tip_young", style={"cursor": "help"})]),
                                                     "value": "young_minutes"},
                                                    {"label": html.Span(["Veteranos produtivos ", html.Span("ⓘ", id="tip_vet", style={"cursor": "help"})]),
                                                     "value": "veterans_prod"},
                                                    {"label": html.Span(["Baixo custo + alto rating ", html.Span("ⓘ", id="tip_cb", style={"cursor": "help"})]),
                                                     "value": "cost_benefit"},
                                                    {"label": html.Span(["Outliers positivos ", html.Span("ⓘ", id="tip_out", style={"cursor": "help"})]),
                                                     "value": "positive_outliers"},
                                                    {"label": html.Span(["Value/Performance ", html.Span("ⓘ", id="tip_vp", style={"cursor": "help"})]),
                                                     "value": "value_perf"},
                                                    {"label": html.Span(["Top 12 ligas (Brasil/ARG/MEX/MLS + top 8 Europa) ", html.Span("ⓘ", id="tip_top12", style={"cursor": "help"})]),
                                                     "value": "top12_leagues"},
                                                ],
                                                value=[],
                                                inputStyle={"marginRight": "6px"},
                                                labelStyle={"display": "block"},
                                            ),
                                            dbc.Tooltip("Filtra jogadores jovens (idade ≤ X) com muitos minutos (minutos ≥ Y).", target="tip_young", placement="right"),
                                            dbc.Tooltip("Filtra veteranos (idade ≥ X) com produção mínima (gols+assists ≥ Y).", target="tip_vet", placement="right"),
                                            dbc.Tooltip("Seleciona jogadores no percentil superior do ratio rating/market value.", target="tip_cb", placement="right"),
                                            dbc.Tooltip("Outlier positivo baseado em z-score (rating e, se existir, GA/90).", target="tip_out", placement="right"),
                                            dbc.Tooltip("Filtra os melhores no ratio rating/market value (value_performance).", target="tip_vp", placement="right"),
                                            dbc.Tooltip(
                                                "Aplica um corte extra para manter somente as ligas listadas explicitamente (sem pattern).",
                                                target="tip_top12",
                                                placement="right"
                                            ),
                                            html.Div("Ative filtros avançados derivados.", className="text-muted small-help mt-1"),
                                        ],
                                        md=6
                                    ),
                                    dbc.Col(
                                        dbc.Card(
                                            dbc.CardBody(
                                                [
                                                    html.Div("Parâmetros dos smart filters", className="fw-semibold mb-2"),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    html.Small("Young: idade ≤", className="text-muted"),
                                                                    dcc.Input(id="young_age_max", type="number", value=23, min=15, max=45, step=1, className="form-control"),
                                                                ],
                                                                md=4
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Small("Young: minutos ≥", className="text-muted"),
                                                                    dcc.Input(id="young_min_min", type="number", value=1000, min=0, step=50, className="form-control"),
                                                                ],
                                                                md=4
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Small("Veteran: idade ≥", className="text-muted"),
                                                                    dcc.Input(id="vet_age_min", type="number", value=30, min=20, max=45, step=1, className="form-control"),
                                                                ],
                                                                md=4
                                                            ),
                                                        ],
                                                        className="g-2 mb-2"
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    html.Small("Veteran: G+A ≥", className="text-muted"),
                                                                    dcc.Input(id="vet_ga_min", type="number", value=10, min=0, step=1, className="form-control"),
                                                                ],
                                                                md=4
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Small("Percentil (≥)", className="text-muted"),
                                                                    dcc.Input(id="cb_pct", type="number", value=75, min=50, max=99, step=1, className="form-control"),
                                                                ],
                                                                md=4
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Small("Outlier z-score ≥", className="text-muted"),
                                                                    dcc.Input(id="outlier_z", type="number", value=1.5, min=0.5, max=5.0, step=0.1, className="form-control"),
                                                                ],
                                                                md=4
                                                            ),
                                                        ],
                                                        className="g-2"
                                                    ),
                                                ]
                                            ),
                                            className="border-0"
                                        ),
                                        md=6
                                    ),
                                ],
                                className="g-3"
                            ),
                        ]
                    ),
                ]
            ),
            className="mb-3"
        ),

        # BAR
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(html.H5("Top jogadores (Bar)", className="mb-2"), md=6),
                                        dbc.Col(
                                            [
                                                html.Label("Qtd. jogadores (Top N)", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    options=[{"label": str(n), "value": n} for n in [10, 15, 20, 30]],
                                                    value=10,
                                                    clearable=False,
                                                    id="bar_top_n",
                                                ),
                                                html.Div("Quantos jogadores aparecem no gráfico.", className="text-muted small-help"),
                                            ],
                                            md=3
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Métrica do eixo Y", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    options=[{"label": c, "value": c} for c in axis_options],
                                                    value=default_bar_metric,
                                                    clearable=False,
                                                    id="bar_metric",
                                                ),
                                                html.Div("Escolha qual estatística exibir.", className="text-muted small-help"),
                                            ],
                                            md=3
                                        ),
                                    ],
                                    className="g-2 align-items-start"
                                ),
                                dcc.Graph(
                                    id="bar_chart",
                                    config={"displayModeBar": True, "displaylogo": False, "responsive": True},
                                ),
                                html.Small("Clique numa barra para selecionar e filtrar a tabela.", className="text-muted"),
                            ]
                        )
                    ),
                    md=12
                ),
            ],
            className="g-3 mb-3"
        ),

        # RADAR
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5("Comparação (Radar)", className="mb-2"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Label("Jogadores (2 a 5)", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="compare_players",
                                                    options=players_opts,
                                                    value=[],
                                                    multi=True,
                                                    placeholder="Selecione 2 a 5 jogadores",
                                                ),
                                                html.Div("Selecione os jogadores a comparar.", className="text-muted small-help"),
                                            ],
                                            md=5
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Preset por posição (preenche métricas)", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="radar_pos_preset",
                                                    options=preset_pos_opts,
                                                    value=None,
                                                    clearable=True,
                                                    placeholder="Escolha uma posição",
                                                ),
                                                html.Div("Ao escolher, as métricas do radar são preenchidas automaticamente.", className="text-muted small-help"),
                                            ],
                                            md=3
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Métricas do radar", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="radar_metrics",
                                                    options=[{"label": c, "value": c} for c in axis_options],
                                                    # ✅ ALTERAÇÃO (1): default per90
                                                    value=[c for c in [
                                                        "rating",
                                                        "goals_per90",
                                                        "assists_per90",
                                                        "expectedgoals_per90",
                                                        "expectedassists_per90",
                                                        "shotsontarget_per90",
                                                        "keypasses_per90",
                                                    ] if c in axis_options][:6],
                                                    multi=True,
                                                    placeholder="Escolha métricas",
                                                ),
                                                html.Div("Recomendado 4–7 métricas.", className="text-muted small-help"),
                                            ],
                                            md=4
                                        ),
                                    ],
                                    className="g-2 mb-2"
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Label("Baseline", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="compare_baseline",
                                                    # ✅ ALTERAÇÃO (2): baseline = posição na liga + posição no mundo
                                                    options=[
                                                        {"label": "Sem baseline", "value": "none"},
                                                        {"label": "Média da posição (liga + mundo)", "value": "pos_league_world"},
                                                    ],
                                                    value="pos_league_world",
                                                    clearable=False,
                                                ),
                                                html.Div("Baselines do 1º jogador: posição na liga + posição no mundo.", className="text-muted small-help"),
                                            ],
                                            md=4
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Normalização", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="radar_norm",
                                                    options=[
                                                        {"label": "Normalizar (0–100) por métrica", "value": "norm"},
                                                        {"label": "Bruto (não recomendado)", "value": "raw"},
                                                    ],
                                                    value="norm",
                                                    clearable=False,
                                                ),
                                                html.Div("Normalizado compara métricas diferentes melhor.", className="text-muted small-help"),
                                            ],
                                            md=4
                                        ),
                                        dbc.Col(
                                            dbc.Button("Aplicar comparação", id="apply_compare", color="primary", className="mt-4"),
                                            md="auto"
                                        ),
                                    ],
                                    className="g-2 align-items-start mb-2"
                                ),

                                dcc.Graph(
                                    id="radar_plot",
                                    config={"displayModeBar": True, "displaylogo": False, "responsive": True},
                                ),

                                html.Hr(),
                                html.H6("Tabela auxiliar (Radar)", className="mb-2"),
                                dash_table.DataTable(
                                    id="radar_table",
                                    columns=[],
                                    data=[],
                                    page_action="none",
                                    sort_action="native",
                                    style_table={"overflowX": "auto"},
                                    style_cell={
                                        "padding": "8px",
                                        "fontFamily": "Segoe UI, Arial",
                                        "fontSize": 13,
                                        "whiteSpace": "nowrap",
                                        "maxWidth": 220,
                                        "overflow": "hidden",
                                        "textOverflow": "ellipsis",
                                        "color": "#1f2d3d",
                                        "backgroundColor": "rgba(255,255,255,0.0)",
                                    },
                                    style_header={
                                        "fontWeight": "700",
                                        "backgroundColor": "rgba(255,255,255,0.75)",
                                        "border": "1px solid rgba(0,0,0,0.06)",
                                        "color": "#1f2d3d",
                                    },
                                    style_data={
                                        "border": "1px solid rgba(0,0,0,0.05)",
                                        "backgroundColor": "rgba(255,255,255,0.0)",
                                    },
                                    style_data_conditional=[
                                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(0,0,0,0.03)"},
                                    ],
                                ),
                                html.Div(id="radar_table_info", className="text-muted mt-2"),
                            ]
                        )
                    ),
                    md=12
                ),
            ],
            className="g-3 mb-3"
        ),

        # SIMILAR
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5("Similar players / Substitutos", className="mb-2"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Label("Jogador âncora", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="anchor_player",
                                                    options=players_opts,
                                                    placeholder="Escolha o jogador âncora",
                                                    value=None,
                                                    clearable=True,
                                                ),
                                                html.Div("Quem você quer substituir/achar similares.", className="text-muted small-help"),
                                            ],
                                            md=4
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Preset por posição (preenche métricas)", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="sim_pos_preset",
                                                    options=preset_pos_opts,
                                                    value=None,
                                                    clearable=True,
                                                    placeholder="Escolha uma posição",
                                                ),
                                                html.Div("Ao escolher, preenche as métricas de similaridade.", className="text-muted small-help"),
                                            ],
                                            md=3
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Métricas usadas", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="sim_metrics",
                                                    options=[{"label": c, "value": c} for c in axis_options],
                                                    # ✅ ALTERAÇÃO (1): default per90
                                                    value=[c for c in [
                                                        "rating",
                                                        "goals_per90",
                                                        "assists_per90",
                                                        "expectedgoals_per90",
                                                        "expectedassists_per90",
                                                        "keypasses_per90",
                                                        "shotsontarget_per90",
                                                        "defensive_actions_per90",
                                                    ] if c in axis_options][:6],
                                                    multi=True,
                                                ),
                                                html.Div("Quais estatísticas definem ‘similaridade’.", className="text-muted small-help"),
                                            ],
                                            md=3
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Qtd. retornada (Top N)", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    id="sim_topn",
                                                    options=[{"label": str(n), "value": n} for n in [10, 20, 30]],
                                                    value=10,
                                                    clearable=False,
                                                ),
                                                html.Div("Quantos similares mostrar.", className="text-muted small-help"),
                                            ],
                                            md=2
                                        ),
                                    ],
                                    className="g-2 mb-2"
                                ),
                                dash_table.DataTable(
                                    id="similar_table",
                                    columns=[
                                        {"name": "playername", "id": "playername"},
                                        {"name": "teamname", "id": "teamname"},
                                        {"name": "leaguename", "id": "leaguename"},
                                        {"name": "positionsdetailed", "id": "positionsdetailed"},
                                        {"name": "Perfil", "id": "perfil", "presentation": "markdown"},
                                        {"name": "SofaScore", "id": "sofascore", "presentation": "markdown"},
                                    ],
                                    data=[],
                                    page_action="none",
                                    sort_action="native",
                                    filter_action="none",
                                    markdown_options={"link_target": "_blank"},
                                    style_table={"overflowX": "auto"},
                                    style_cell={
                                        "padding": "8px",
                                        "fontFamily": "Segoe UI, Arial",
                                        "fontSize": 13,
                                        "whiteSpace": "nowrap",
                                        "maxWidth": 240,
                                        "overflow": "hidden",
                                        "textOverflow": "ellipsis",
                                        "color": "#1f2d3d",
                                        "backgroundColor": "rgba(255,255,255,0.0)",
                                    },
                                    style_header={
                                        "fontWeight": "700",
                                        "backgroundColor": "rgba(255,255,255,0.75)",
                                        "border": "1px solid rgba(0,0,0,0.06)",
                                        "color": "#1f2d3d",
                                    },
                                    style_data={
                                        "border": "1px solid rgba(0,0,0,0.05)",
                                        "backgroundColor": "rgba(255,255,255,0.0)",
                                    },
                                    style_data_conditional=[
                                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(0,0,0,0.03)"},
                                    ],
                                ),
                                html.Div(id="similar_info", className="text-muted mt-2"),
                            ]
                        )
                    ),
                    md=12
                ),
            ],
            className="g-3 mb-3"
        ),

        # SCATTER
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5("Dispersão (Scatter)", className="mb-2"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Label("Eixo X", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    options=[{"label": c, "value": c} for c in axis_options],
                                                    value=default_scatter_x,
                                                    clearable=False,
                                                    id="scatter_x",
                                                ),
                                                html.Div("Métrica exibida no eixo horizontal.", className="text-muted small-help"),
                                            ],
                                            md=4
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Eixo Y", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    options=[{"label": c, "value": c} for c in axis_options],
                                                    value=default_scatter_y,
                                                    clearable=False,
                                                    id="scatter_y",
                                                ),
                                                html.Div("Métrica exibida no eixo vertical.", className="text-muted small-help"),
                                            ],
                                            md=4
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Limite de pontos", className="fw-semibold"),
                                                dcc.Dropdown(
                                                    options=[{"label": str(n), "value": n} for n in [500, 1000, 3000, 999999]],
                                                    value=1000,
                                                    clearable=False,
                                                    id="scatter_max_points",
                                                ),
                                                html.Div("Amostragem para performance.", className="text-muted small-help"),
                                            ],
                                            md=4
                                        ),
                                    ],
                                    className="g-2"
                                ),
                                dcc.Graph(
                                    id="scatter_plot",
                                    config={"displayModeBar": True, "displaylogo": False, "responsive": True},
                                ),
                                html.Small("Use Box/Lasso para selecionar e filtrar a tabela.", className="text-muted"),
                            ]
                        )
                    ),
                    md=12
                ),
            ],
            className="g-3 mb-3"
        ),

        # MAIN TABLE
        dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(html.H5("Tabela (campos principais)", className="mb-2"), md=8),
                            dbc.Col(
                                [
                                    html.Label("Qtd. exibida", className="fw-semibold"),
                                    dcc.Dropdown(
                                        options=[{"label": str(n), "value": n} for n in [25, 50, 100, 150, 300]],
                                        value=25,
                                        clearable=False,
                                        id="table_n",
                                    ),
                                    html.Div("Após filtros e seleção.", className="text-muted small-help"),
                                ],
                                md=4
                            )
                        ],
                        className="g-2 align-items-start mb-2"
                    ),
                    dash_table.DataTable(
                        id="main_table",
                        columns=[
                            {
                                "name": ("Perfil" if c == "perfil" else ("SofaScore" if c == "sofascore" else c)),
                                "id": c,
                                "presentation": ("markdown" if c in ["sofascore", "perfil"] else "input")
                            }
                            for c in IMPORTANT_COLS
                        ],
                        data=[],
                        page_action="none",
                        sort_action="native",
                        filter_action="native",
                        markdown_options={"link_target": "_blank"},
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "padding": "8px",
                            "fontFamily": "Segoe UI, Arial",
                            "fontSize": 13,
                            "whiteSpace": "nowrap",
                            "maxWidth": 240,
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "color": "#1f2d3d",
                            "backgroundColor": "rgba(255,255,255,0.0)",
                        },
                        style_header={
                            "fontWeight": "700",
                            "backgroundColor": "rgba(255,255,255,0.75)",
                            "border": "1px solid rgba(0,0,0,0.06)",
                            "color": "#1f2d3d",
                        },
                        style_data={
                            "border": "1px solid rgba(0,0,0,0.05)",
                            "backgroundColor": "rgba(255,255,255,0.0)",
                        },
                        style_data_conditional=[
                            {"if": {"row_index": "odd"}, "backgroundColor": "rgba(0,0,0,0.03)"},
                        ],
                    ),
                    html.Div(id="row_count_info", className="text-muted mt-2"),
                ]
            )
        ),
    ],
    style={"maxWidth": "1600px"}
)

# =========================
# CALLBACKS (HOME)
# =========================
@dash.callback(
    Output("smart_collapse", "is_open"),
    Input("toggle_smart", "n_clicks"),
    State("smart_collapse", "is_open"),
)
def toggle_smart(n, is_open):
    if not n:
        return is_open
    return not is_open

@dash.callback(
    Output("age_band", "value"),
    Output("min_band", "value"),
    Output("league_filter", "value"),
    Output("pos_filter", "value"),
    Output("country_filter", "value"),
    Output("mv_band", "value"),
    Output("rating_min_band", "value"),
    Output("smart_filters", "value"),
    Output("young_age_max", "value"),
    Output("young_min_min", "value"),
    Output("vet_age_min", "value"),
    Output("vet_ga_min", "value"),
    Output("cb_pct", "value"),
    Output("outlier_z", "value"),
    Input("clear_filters", "n_clicks"),
    prevent_initial_call=True
)
def clear_all_filters(_):
    return (
        None, None, None, None,
        None,
        "ALL", "NONE",
        [],
        23, 1000, 30, 10,
        75, 1.5
    )

@dash.callback(
    Output("radar_metrics", "value"),
    Input("radar_pos_preset", "value"),
    State("radar_metrics", "value"),
    prevent_initial_call=True
)
def apply_radar_preset(pos_code, current):
    if not pos_code:
        return no_update
    return preset_metrics_for_pos(pos_code, max_len=7)

@dash.callback(
    Output("sim_metrics", "value"),
    Input("sim_pos_preset", "value"),
    State("sim_metrics", "value"),
    prevent_initial_call=True
)
def apply_sim_preset(pos_code, current):
    if not pos_code:
        return no_update
    return preset_metrics_for_pos(pos_code, max_len=6)

@dash.callback(
    Output("compare_players", "options"),
    Output("compare_players", "value"),
    Output("anchor_player", "options"),
    Output("anchor_player", "value"),
    Input("age_band", "value"),
    Input("min_band", "value"),
    Input("league_filter", "value"),
    Input("pos_filter", "value"),
    Input("country_filter", "value"),
    Input("mv_band", "value"),
    Input("rating_min_band", "value"),
    Input("smart_filters", "value"),
    Input("young_age_max", "value"),
    Input("young_min_min", "value"),
    Input("vet_age_min", "value"),
    Input("vet_ga_min", "value"),
    Input("cb_pct", "value"),
    Input("outlier_z", "value"),
    State("compare_players", "value"),
    State("anchor_player", "value"),
)
def sync_player_dropdowns(
    age_band, min_band, leagues, positions, countries, mv_band_key, rating_min_key, smart_filters,
    young_age_max, young_min_min, vet_age_min, vet_ga_min, cb_pct, outlier_z,
    compare_players_value, anchor_player_value
):
    dff = apply_filters(
        df,
        age_band, min_band, leagues, positions, countries,
        mv_band_key, rating_min_key,
        smart_filters or [],
        int(young_age_max or 23),
        int(young_min_min or 1000),
        int(vet_age_min or 30),
        float(vet_ga_min or 10),
        int(cb_pct or 75),
        float(outlier_z or 1.5)
    )

    opts = make_player_options(dff)
    allowed = set(o["value"] for o in opts)

    compare_players_value = compare_players_value or []
    new_compare = []
    for x in compare_players_value:
        try:
            ix = int(x)
            if ix in allowed:
                new_compare.append(ix)
        except Exception:
            pass

    new_anchor = None
    if anchor_player_value is not None:
        try:
            ax = int(anchor_player_value)
            if ax in allowed:
                new_anchor = ax
        except Exception:
            new_anchor = None

    return opts, new_compare, opts, new_anchor

@dash.callback(
    Output("selected_ids_store", "data"),
    Output("selection_info", "children"),
    Input("scatter_plot", "selectedData"),
    Input("bar_chart", "clickData"),
    Input("clear_selection", "n_clicks"),
    State("selected_ids_store", "data"),
)
def update_selected_ids(scatter_selected, bar_click, clear_clicks, current_store):
    trig = callback_context.triggered[0]["prop_id"] if callback_context.triggered else ""

    if trig == "clear_selection.n_clicks":
        return [], "Seleção limpa."

    current_store = current_store or []

    if trig == "bar_chart.clickData" and bar_click and isinstance(bar_click, dict):
        try:
            pt = bar_click.get("points", [])[0] if bar_click.get("points") else None
            if pt and "x" in pt:
                label = pt["x"]
                return {"type": "bar_label", "value": label}, f"Selecionado via barra: {label}"
        except Exception:
            pass
        return current_store, "Clique detectado, mas não foi possível resolver o jogador."

    if trig == "scatter_plot.selectedData":
        selected_ids = []
        if scatter_selected and isinstance(scatter_selected, dict) and "points" in scatter_selected:
            for p in scatter_selected.get("points", []):
                cd = p.get("customdata")
                if cd and len(cd) > 0 and cd[0] is not None:
                    try:
                        selected_ids.append(int(cd[0]))
                    except Exception:
                        pass
        if selected_ids:
            return {"type": "ids", "value": sorted(list(set(selected_ids)))}, f"Selecionados no scatter: {len(set(selected_ids))}"
        else:
            return current_store, "Seleção no scatter vazia (mantendo seleção persistida)."

    return current_store, no_update

@dash.callback(
    Output("bar_chart", "figure"),
    Output("scatter_plot", "figure"),
    Output("main_table", "data"),
    Output("row_count_info", "children"),
    Output("similar_table", "data"),
    Output("similar_info", "children"),
    Output("radar_plot", "figure"),
    Output("radar_table", "columns"),
    Output("radar_table", "data"),
    Output("radar_table_info", "children"),
    Input("age_band", "value"),
    Input("min_band", "value"),
    Input("league_filter", "value"),
    Input("pos_filter", "value"),
    Input("country_filter", "value"),
    Input("mv_band", "value"),
    Input("rating_min_band", "value"),
    Input("smart_filters", "value"),
    Input("young_age_max", "value"),
    Input("young_min_min", "value"),
    Input("vet_age_min", "value"),
    Input("vet_ga_min", "value"),
    Input("cb_pct", "value"),
    Input("outlier_z", "value"),
    Input("bar_metric", "value"),
    Input("bar_top_n", "value"),
    Input("scatter_x", "value"),
    Input("scatter_y", "value"),
    Input("scatter_max_points", "value"),
    Input("table_n", "value"),
    Input("selected_ids_store", "data"),
    Input("anchor_player", "value"),
    Input("sim_metrics", "value"),
    Input("sim_topn", "value"),
    Input("apply_compare", "n_clicks"),
    State("compare_players", "value"),
    State("radar_metrics", "value"),
    State("compare_baseline", "value"),
    State("radar_norm", "value"),
    State("radar_pos_preset", "value"),
)
def update_all(
    age_band, min_band, leagues, positions, countries, mv_band_key, rating_min_key, smart_filters,
    young_age_max, young_min_min, vet_age_min, vet_ga_min, cb_pct, outlier_z,
    bar_metric, bar_top_n,
    scatter_x, scatter_y, scatter_max_points,
    table_n, selected_store,
    anchor_player, sim_metrics, sim_topn,
    apply_compare_clicks, compare_players, radar_metrics, compare_baseline, radar_norm, radar_pos_preset
):
    dff = apply_filters(
        df,
        age_band, min_band, leagues, positions, countries,
        mv_band_key, rating_min_key,
        smart_filters or [],
        int(young_age_max or 23),
        int(young_min_min or 1000),
        int(vet_age_min or 30),
        float(vet_ga_min or 10),
        int(cb_pct or 75),
        float(outlier_z or 1.5)
    )

    selected_ids = set()
    if isinstance(selected_store, dict) and selected_store.get("type") == "ids":
        selected_ids = set(selected_store.get("value") or [])
    elif isinstance(selected_store, list):
        selected_ids = set([int(x) for x in selected_store if x is not None])

    # BAR
    dff_bar = dff.copy()
    if bar_metric is None or bar_metric not in dff_bar.columns or dff_bar[bar_metric].dropna().empty:
        fig_bar = px.bar(title="Sem dados para os filtros atuais.")
        fig_bar.update_layout(template="plotly_white", height=420, margin=dict(l=10, r=10, t=40, b=10),
                             paper_bgcolor="white", plot_bgcolor="white")
        df_bar_shown = dff_bar
    else:
        dff_bar = dff_bar.dropna(subset=[bar_metric])
        dff_bar["player_label"] = dff_bar["playername"].astype(str) + " — " + dff_bar["teamname"].astype(str)
        dff_bar = dff_bar.sort_values(bar_metric, ascending=False).head(int(bar_top_n or 10))
        df_bar_shown = dff_bar

        fig_bar = px.bar(
            dff_bar,
            x="player_label",
            y=bar_metric,
            title=f"Top {bar_top_n} por {bar_metric}",
            hover_data=["age", "leaguename", "minutesplayed"] if "minutesplayed" in dff_bar.columns else ["age", "leaguename"],
        )
        fig_bar.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(l=10, r=10, t=50, b=110),
            xaxis_title="Jogador",
            yaxis_title=bar_metric,
            paper_bgcolor="white",
            plot_bgcolor="white",
            uirevision="bar-keep"
        )
        fig_bar.update_xaxes(tickangle=-45)

    if isinstance(selected_store, dict) and selected_store.get("type") == "bar_label":
        label = selected_store.get("value")
        if label and "player_label" in df_bar_shown.columns:
            hit = df_bar_shown[df_bar_shown["player_label"] == label]
            if not hit.empty:
                selected_ids = set(hit["_row_id"].astype("int64").tolist())

    # SCATTER
    if scatter_x is None or scatter_y is None or scatter_x not in dff.columns or scatter_y not in dff.columns or dff[[scatter_x, scatter_y]].dropna().empty:
        fig_scatter = px.scatter(title="Sem dados para os filtros atuais.")
        fig_scatter.update_layout(template="plotly_white", height=420, margin=dict(l=10, r=10, t=40, b=10),
                                 paper_bgcolor="white", plot_bgcolor="white")
    else:
        dff_sc = dff.dropna(subset=[scatter_x, scatter_y]).copy()
        max_pts = int(scatter_max_points or 1000)
        if len(dff_sc) > max_pts and max_pts < 999999:
            dff_sc = dff_sc.sample(n=max_pts, random_state=42)

        fig_scatter = px.scatter(
            dff_sc,
            x=scatter_x,
            y=scatter_y,
            hover_name="playername",
            hover_data={
                "teamname": True,
                "leaguename": True,
                "country": True if "country" in dff_sc.columns else False,
                "age": True,
                "minutesplayed": True if "minutesplayed" in dff_sc.columns else False,
                "pos_pt_main": True,
                scatter_x: True,
                scatter_y: True,
            },
            color="pos_pt_main",
            title=f"{scatter_y} vs {scatter_x}",
            custom_data=["_row_id"],
        )
        fig_scatter.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(l=10, r=10, t=50, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            legend_title_text="Posição",
            uirevision="scatter-keep"
        )

    # MAIN TABLE
    dff_tbl_base = dff.copy()
    if selected_ids:
        dff_tbl_base = dff_tbl_base[dff_tbl_base["_row_id"].isin(selected_ids)]

    if "rating" in dff_tbl_base.columns:
        dff_tbl_base = dff_tbl_base.sort_values("rating", ascending=False)

    # ✅ ALTERAÇÃO (3): cria coluna Perfil com link
    dff_tbl_base = dff_tbl_base.copy()
    if "_row_id" in dff_tbl_base.columns:
        dff_tbl_base["perfil"] = dff_tbl_base["_row_id"].apply(lambda pid: f"[Abrir](/jogador/{int(pid)})")
    else:
        dff_tbl_base["perfil"] = ""

    dff_tbl = dff_tbl_base[IMPORTANT_COLS].head(int(table_n or 50))
    table_data = dff_tbl.to_dict("records")

    info = (
        f"Filtrados: {len(dff):,} jogadores"
        + f" | Selecionados: {len(selected_ids):,}"
        + f" | Exibindo: {min(len(dff_tbl_base), int(table_n or 50)):,}"
    )

    # SIMILAR
    sim_data = []
    sim_info = "Escolha um jogador âncora para ver similares."
    if anchor_player is not None and sim_metrics:
        dff_sim = dff.copy()
        if anchor_player in dff_sim["_row_id"].values:
            feats = [m for m in sim_metrics if m in dff_sim.columns]

            X = dff_sim[feats].replace([np.inf, -np.inf], np.nan).astype(float)
            ok = X.notna().all(axis=1)
            dff_ok = dff_sim[ok].copy()
            X_ok = X[ok].copy()

            if not dff_ok.empty and int(anchor_player) in dff_ok["_row_id"].values:
                mu = X_ok.mean(axis=0)
                sd = X_ok.std(axis=0).replace(0, 1.0)
                Z = (X_ok - mu) / sd

                a_idx = dff_ok.index[dff_ok["_row_id"] == int(anchor_player)][0]
                a_vec = Z.loc[a_idx].to_numpy()

                dist = np.sqrt(((Z.to_numpy() - a_vec) ** 2).sum(axis=1))
                dff_ok["distance"] = dist

                dff_ok = dff_ok[dff_ok["_row_id"] != int(anchor_player)].copy()
                dff_ok = dff_ok.sort_values("distance", ascending=True).head(int(sim_topn or 10))

                cols = ["playername", "teamname", "leaguename", "positionsdetailed", "distance", "sofascore"]
                cols = [c for c in cols if c in dff_ok.columns]
                dff_show = dff_ok[cols].copy()
                dff_show["perfil"] = dff_ok["_row_id"].apply(lambda pid: f"[Abrir](/jogador/{int(pid)})")
                if "distance" in dff_show.columns:
                    dff_show["distance"] = dff_show["distance"].round(4)

                sim_data = dff_show.to_dict("records")
                sim_info = f"Top {len(sim_data)} similares usando {len(feats)} métricas."
            else:
                sim_info = "Âncora sem dados completos nas métricas escolhidas (ou foi filtrado)."
        else:
            sim_info = "Âncora não está no conjunto filtrado atual."

    # RADAR
    radar_table_columns = []
    radar_table_data = []
    radar_table_info = "Clique em ‘Aplicar comparação’ para preencher a tabela."

    fig_radar = go.Figure()
    fig_radar.update_layout(
        template="plotly_white",
        height=520,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        title="Selecione jogadores/métricas e clique em ‘Aplicar comparação’.",
        polar=dict(radialaxis=dict(visible=True, showticklabels=False))
    )

    trig = callback_context.triggered[0]["prop_id"] if callback_context.triggered else ""
    if trig == "apply_compare.n_clicks" and compare_players and radar_metrics:
        ids = [int(x) for x in compare_players][:5]
        feats = [m for m in radar_metrics if m in dff.columns]

        if len(ids) >= 2 and len(feats) >= 3:
            dff_r = dff[dff["_row_id"].isin(ids)].copy()
            if not dff_r.empty:
                M_raw = dff_r[feats].replace([np.inf, -np.inf], np.nan).astype(float)

                base_rows = []  # lista de (label, series_raw)

                first = dff_r.iloc[0]
                pos_code = first.get("pos_code_main") if "pos_code_main" in dff.columns else None
                league = first.get("leaguename") if "leaguename" in dff.columns else None

                # ✅ ALTERAÇÃO (2): baseline = posição na liga + posição no mundo
                if compare_baseline == "pos_league_world" and pos_code is not None:
                    # Posição na liga
                    if league is not None:
                        ctx_league = dff[(dff.get("pos_code_main") == pos_code) & (dff.get("leaguename") == league)].copy()
                        if not ctx_league.empty:
                            s_league = ctx_league[feats].replace([np.inf, -np.inf], np.nan).astype(float).mean(axis=0, skipna=True)
                            base_rows.append((f"Média da posição na liga — {pos_to_pt(pos_code)} | {league}", s_league))

                    # Posição no mundo
                    ctx_world = dff[dff.get("pos_code_main") == pos_code].copy()
                    if not ctx_world.empty:
                        s_world = ctx_world[feats].replace([np.inf, -np.inf], np.nan).astype(float).mean(axis=0, skipna=True)
                        base_rows.append((f"Média da posição no mundo — {pos_to_pt(pos_code)}", s_world))

                if radar_norm == "norm":
                    base_ref = dff[feats].replace([np.inf, -np.inf], np.nan).astype(float)

                    # ✅ usa percentis para evitar outliers esmagando a escala
                    p_low  = base_ref.quantile(0.05)
                    p_high = base_ref.quantile(0.95)

                    # evita denom 0
                    denom = (p_high - p_low).replace(0, 1.0)

                    # clamp (winsorize) antes de escalar
                    M_clip = M_raw.clip(lower=p_low, upper=p_high, axis=1)
                    M_scaled = (M_clip - p_low) / denom * 100.0

                    base_scaled_rows = []
                    for lbl, s_raw in base_rows:
                        s_clip = s_raw.clip(lower=p_low, upper=p_high)
                        base_scaled_rows.append((lbl, (s_clip - p_low) / denom * 100.0))
                else:
                    M_scaled = M_raw.copy()
                    base_scaled_rows = [(lbl, s_raw) for (lbl, s_raw) in base_rows]

                rows_tbl = []

                # Tabela: baselines primeiro
                for lbl, s_raw in base_rows:
                    row = {"entity": lbl, "type": "baseline"}
                    for f in feats:
                        v = s_raw.get(f, np.nan)
                        row[f] = (None if pd.isna(v) else float(v))
                    rows_tbl.append(row)

                # Tabela: jogadores
                for idx, r in dff_r.iterrows():
                    nm = f"{r.get('playername','')} — {r.get('teamname','')}"
                    row = {"entity": nm, "type": "player"}
                    row_raw = M_raw.loc[idx]
                    for f in feats:
                        v = row_raw.get(f, np.nan)
                        row[f] = (None if pd.isna(v) else float(v))
                    rows_tbl.append(row)

                radar_table_columns = [{"name": "entity", "id": "entity"}, {"name": "type", "id": "type"}] + [
                    {"name": f, "id": f, "type": "numeric"} for f in feats
                ]
                radar_table_data = rows_tbl
                radar_table_info = f"{len(rows_tbl)} linhas (baselines + jogadores) | {len(feats)} métricas."

                cats = feats + [feats[0]]
                fig_radar = go.Figure()

                # Jogadores
                for idx, r in dff_r.iterrows():
                    row_scaled = M_scaled.loc[idx]
                    row_raw = M_raw.loc[idx]

                    vals_scaled = [
                        float(row_scaled.get(f, 0.0)) if pd.notna(row_scaled.get(f, np.nan)) else 0.0
                        for f in feats
                    ]
                    vals_raw = [
                        float(row_raw.get(f, np.nan)) if pd.notna(row_raw.get(f, np.nan)) else np.nan
                        for f in feats
                    ]

                    vals_scaled_loop = vals_scaled + [vals_scaled[0]]
                    vals_raw_loop = vals_raw + [vals_raw[0]]

                    name = f"{r.get('playername','')} — {r.get('teamname','')}"
                    customdata = np.array(vals_raw_loop, dtype=float)

                    hovertemplate = (
                        "<b>%{fullData.name}</b><br>"
                        "Métrica: %{theta}<br>"
                        "Normalizado: %{r:.2f}"
                        "<br>Valor real: %{customdata:.2g}"
                        "<extra></extra>"
                    ) if radar_norm == "norm" else (
                        "<b>%{fullData.name}</b><br>"
                        "Métrica: %{theta}<br>"
                        "Valor: %{r:.4g}"
                        "<extra></extra>"
                    )

                    fig_radar.add_trace(
                        go.Scatterpolar(
                            r=vals_scaled_loop,
                            theta=cats,
                            fill="toself",
                            name=name,
                            customdata=customdata,
                            hovertemplate=hovertemplate
                        )
                    )

                # Baselines (liga + mundo)
                dash_styles = ["dash", "dot", "dashdot"]
                for i, (lbl, s_scaled) in enumerate(base_scaled_rows):
                    # precisa do raw também pro hover real
                    s_raw = dict(base_rows)[lbl] if base_rows else None

                    vals_scaled = [
                        float(s_scaled.get(f, 0.0)) if pd.notna(s_scaled.get(f, np.nan)) else 0.0
                        for f in feats
                    ]
                    vals_scaled_loop = vals_scaled + [vals_scaled[0]]

                    if s_raw is not None:
                        vals_raw = [
                            float(s_raw.get(f, np.nan)) if pd.notna(s_raw.get(f, np.nan)) else np.nan
                            for f in feats
                        ]
                        vals_raw_loop = vals_raw + [vals_raw[0]]
                        customdata = np.array(vals_raw_loop, dtype=float)
                    else:
                        customdata = np.array([np.nan] * len(vals_scaled_loop), dtype=float)

                    hovertemplate = (
                        "<b>%{fullData.name}</b><br>"
                        "Métrica: %{theta}<br>"
                        "Normalizado: %{r:.2f}"
                        "<br>Valor real: %{customdata:.2g}"
                        "<extra></extra>"
                    ) if radar_norm == "norm" else (
                        "<b>%{fullData.name}</b><br>"
                        "Métrica: %{theta}<br>"
                        "Valor: %{r:.4g}"
                        "<extra></extra>"
                    )

                    fig_radar.add_trace(
                        go.Scatterpolar(
                            r=vals_scaled_loop,
                            theta=cats,
                            fill=None,
                            name=lbl,
                            customdata=customdata,
                            hovertemplate=hovertemplate,
                            line=dict(dash=dash_styles[i % len(dash_styles)], width=2),
                        )
                    )

                fig_radar.update_layout(
                    template="plotly_white",
                    height=520,
                    margin=dict(l=10, r=10, t=60, b=10),
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    title=f"Radar ({'0–100 por métrica (com valores reais no hover)' if radar_norm=='norm' else 'bruto'})",
                    polar=dict(radialaxis=dict(visible=True, showticklabels=False))
                )

    return (
        fig_bar, fig_scatter, table_data, info,
        sim_data, sim_info,
        fig_radar,
        radar_table_columns, radar_table_data, radar_table_info
    )
