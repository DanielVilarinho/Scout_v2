# pages/jogador.py
import os
import time
import urllib.parse
import requests
import re

import numpy as np
import pandas as pd

import dash
from dash import dcc, html, Input, Output, State
from dash import dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from bs4 import BeautifulSoup

from data import DF, POS_PT

# =========================
# (Opcional) .env support
# =========================
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass


dash.register_page(
    __name__,
    path_template="/jogador/<playerid>",
    name="Jogador",
    title="Jogador",
    order=None,
    hidden=True,
)

df = DF

# =========================
# Config / Presets
# =========================
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

DEFAULT_PRESET = ["rating", "appearances", "goals", "assists"]

LOWER_IS_BETTER = {
    "errorsleadingtogoal", "errorleadtogoal",
    "errorsleadingtoshot",
    "goalsconceded",
    "bigchancesmissed",
    "dribbledpast",
    "redcards",
    "yellowcards",
}

PCT_COLORS = {
    "high":   "#2E7D32",
    "mid_hi": "#1E88E5",
    "mid":    "#607D8B",
    "low":    "#E76F51",
}

PCT_GROUPS = {
    "Finalização": [
        "goals", "goals_per90", "shots", "totalshots", "shotsontarget",
        "shotsfrominsidethebox", "xg", "expectedgoals"
    ],
    "Criação": [
        "assists", "assists_per90", "keypasses", "chancescreated", "bigchancescreated",
        "xa", "expectedassists", "passtoassist"
    ],
    "Passe & Construção": [
        "passes", "totalpasses", "accuratepasses", "passaccuracy", "accuratepassespercentage",
        "totallongballs", "accuratelongballs", "accuratelongballspercentage",
    ],
    "Defesa": [
        "tackles", "interceptions", "clearances", "blockedshots", "outfielderblocks",
        "aerialduelswon", "duelswon", "dribbledpast"
    ],
    "Goleiro": [
        "saves", "savepercentage", "cleansheets", "cleansheet", "goalsconceded"
    ],
    "Disciplina & Erros": [
        "errorsleadingtogoal", "errorleadtogoal", "errorsleadingtoshot",
        "yellowcards", "redcards"
    ],
}

# =========================
# YouTube API
# =========================
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
_YT_CACHE = {}
_YT_CACHE_TTL_SEC = 60 * 60 * 24 * 7
_YT_TIMEOUT = 8
_YT_MAX_RESULTS = 10  # vamos buscar mais para aumentar chance de pegar canais prioritários

# =========================
# YouTube: prioridade de canais (para escolher vídeo principal)
# =========================
PRIORITY_CHANNELS = [
    "360edition",
    "brazil scout",
    "jm productions hd",
    "lutyhd",
]

# =========================
# Transfermarkt (Rumours) - scraping + cache
# =========================
TM_BASE_URL = "https://www.transfermarkt.com"
_TM_TIMEOUT = 12
_TM_SLEEP_SEC = 1.1
_TM_CACHE = {}
_TM_CACHE_TTL_SEC = 60 * 60 * 12  # 12h

_TM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": TM_BASE_URL,
}

_TM_SESSION = requests.Session()
_TM_SESSION.headers.update(_TM_HEADERS)


# =========================
# Helpers
# =========================
def _to_int_safe(x):
    try:
        return int(float(x))
    except Exception:
        return None


def _fmt_num(v):
    if v is None:
        return "NA"
    try:
        if pd.isna(v):
            return "NA"
    except Exception:
        pass

    if isinstance(v, (int, np.integer)):
        return str(int(v))

    try:
        fv = float(v)
        if np.isnan(fv):
            return "NA"
        if fv.is_integer():
            return str(int(fv))
        return f"{fv:.2f}"
    except Exception:
        return str(v)


def _safe_float(v):
    try:
        if v is None:
            return np.nan
        if isinstance(v, str) and not v.strip():
            return np.nan
        fv = float(v)
        if np.isnan(fv) or np.isinf(fv):
            return np.nan
        return fv
    except Exception:
        return np.nan


def _normalize_role_code(code: str) -> str:
    if not code:
        return ""
    c = str(code).upper().strip()

    if c in ["LCB", "RCB", "CB"]:
        return "CB"
    if c in ["LWB", "LB"]:
        return "LB"
    if c in ["RWB", "RB"]:
        return "RB"
    if c in ["CDM", "DM"]:
        return "DM"
    if c in ["CAM", "LAM", "RAM", "AM", "LM", "RM"]:
        return "AM"
    if c in ["CF", "SS", "RF", "LF", "FW", "ST"]:
        return "ST"
    if c == "GK":
        return "GK"
    return c


def _pos_pt(code: str) -> str:
    c = str(code).upper().strip() if code else ""
    return POS_PT.get(c, c or "NA")


def _get_player_row(playerid: str) -> pd.Series | None:
    pid = _to_int_safe(playerid)
    if pid is None or "playerid" not in df.columns:
        return None
    pid_col = pd.to_numeric(df["playerid"], errors="coerce").fillna(-1).astype("int64")
    hit = df[pid_col == pid]
    if hit.empty:
        return None
    return hit.iloc[0]


def _get_pos_code_main(r: pd.Series) -> str:
    if "pos_code_main" in r.index and pd.notna(r.get("pos_code_main")):
        return _normalize_role_code(r.get("pos_code_main"))

    if "position" in r.index and pd.notna(r.get("position")):
        return _normalize_role_code(r.get("position"))

    if "positions_list" in r.index and isinstance(r.get("positions_list"), list) and r.get("positions_list"):
        return _normalize_role_code(r.get("positions_list")[0])

    if "positionsdetailed" in r.index and pd.notna(r.get("positionsdetailed")):
        s = str(r.get("positionsdetailed"))
        if s:
            return _normalize_role_code(s.split(",")[0].strip())

    return ""


def _only_existing_metrics(metrics: list[str], base_df: pd.DataFrame) -> list[str]:
    out = [m for m in metrics if m in base_df.columns]
    seen, final = set(), []
    for m in out:
        if m not in seen:
            final.append(m)
            seen.add(m)
    return final


def _axis_options(base_df: pd.DataFrame) -> list[str]:
    numeric_cols = base_df.select_dtypes(include="number").columns.tolist()
    drop_numeric_like_ids = {"playerid", "teamid", "tournamentid", "seasonid", "dateofbirthtimestamp"}
    return [c for c in numeric_cols if c not in drop_numeric_like_ids]


def _pos_mask_for(pos_code: str, base_df: pd.DataFrame) -> pd.Series:
    if not pos_code:
        return pd.Series([True] * len(base_df), index=base_df.index)

    if "pos_code_main" in base_df.columns:
        return base_df["pos_code_main"].astype(str).str.upper().str.strip() == str(pos_code).upper().strip()

    if "position" in base_df.columns:
        return base_df["position"].astype(str).str.upper().str.strip() == str(pos_code).upper().strip()

    if "positions_list" in base_df.columns:
        return base_df["positions_list"].apply(
            lambda lst: any(str(pos_code).upper() == str(p).upper() for p in (lst or []))
        )

    if "positionsdetailed" in base_df.columns:
        return base_df["positionsdetailed"].astype(str).str.upper().str.contains(str(pos_code).upper(), regex=False)

    return pd.Series([True] * len(base_df), index=base_df.index)


def _league_mask_for(league: str, base_df: pd.DataFrame) -> pd.Series:
    if "leaguename" not in base_df.columns or not league or pd.isna(league):
        return pd.Series([True] * len(base_df), index=base_df.index)
    return base_df["leaguename"] == league


def _minmax_scale_series(series: pd.Series, v: float) -> float:
    s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if s.empty:
        return np.nan
    mn = float(s.min())
    mx = float(s.max())
    if np.isnan(mn) or np.isnan(mx) or mx == mn:
        return 50.0
    return (float(v) - mn) / (mx - mn) * 100.0


def _percentile_of_value(series: pd.Series, v: float, higher_is_better: bool = True) -> float:
    s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if s.empty or v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    vv = float(v)
    if higher_is_better:
        pct = (s < vv).mean() * 100.0
    else:
        pct = (s > vv).mean() * 100.0
    return float(max(0.0, min(100.0, pct)))


def _pct_color(p: float) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return PCT_COLORS["mid"]
    if p >= 90:
        return PCT_COLORS["high"]
    if p >= 60:
        return PCT_COLORS["mid_hi"]
    if p >= 20:
        return PCT_COLORS["mid"]
    return PCT_COLORS["low"]


def _kpi_card(label: str, value: str) -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(label, className="text-muted", style={"fontSize": "12px"}),
                    html.Div(value, className="fw-bold", style={"fontSize": "22px", "lineHeight": "24px"}),
                ],
                className="py-2",
            ),
            style={"borderRadius": "14px"},
            className="h-100",
        ),
        md=3, sm=6, xs=6,
    )


def _similar_players(player_row: pd.Series, pos_code: str, feats: list[str], topk: int = 6) -> pd.DataFrame:
    if "playerid" not in df.columns:
        return pd.DataFrame()

    pid = _to_int_safe(player_row.get("playerid"))
    pos_mask = _pos_mask_for(pos_code, df)
    base = df[pos_mask].copy()
    if base.empty:
        base = df.copy()

    feats = [f for f in feats if f in base.columns]
    if len(feats) < 3:
        feats = _only_existing_metrics(DEFAULT_PRESET, base)
    if len(feats) < 3:
        return pd.DataFrame()

    X = base[feats].apply(pd.to_numeric, errors="coerce")
    mu = X.mean(skipna=True)
    sd = X.std(skipna=True).replace(0, np.nan)
    z = (X - mu) / sd

    pr = pd.to_numeric(pd.Series({f: player_row.get(f, np.nan) for f in feats}), errors="coerce")
    pz = (pr - mu) / sd

    def dist_row(row):
        a = row.values.astype(float)
        b = pz.values.astype(float)
        m = ~np.isnan(a) & ~np.isnan(b)
        if not m.any():
            return np.inf
        d = a[m] - b[m]
        return float(np.sqrt(np.mean(d * d)))

    base = base.copy()
    base["_dist"] = z.apply(dist_row, axis=1)

    pid_col = pd.to_numeric(base["playerid"], errors="coerce").fillna(-1).astype("int64")
    base = base[pid_col != int(pid)] if pid is not None else base
    return base.sort_values("_dist", ascending=True).head(int(topk))


def _compute_percentile_table(player_row: pd.Series, pos_code: str, league: str, pct_feats: list[str], scope: str):
    pos_mask = _pos_mask_for(pos_code, df)
    league_mask = _league_mask_for(league, df)

    world_pos_df = df[pos_mask].copy()
    league_pos_df = df[pos_mask & league_mask].copy()

    if scope == "world_pos":
        pct_df = world_pos_df
        scope_label = "posição no mundo"
    else:
        pct_df = league_pos_df
        scope_label = "posição na liga"
        if pct_df.empty:
            pct_df = world_pos_df
            scope_label = "posição no mundo (fallback: liga vazia)"

    rows = []
    for m in pct_feats:
        pv = pd.to_numeric(pd.Series([player_row.get(m, np.nan)]), errors="coerce").iloc[0]
        higher_is_better = (m not in LOWER_IS_BETTER)
        pct = _percentile_of_value(pct_df.get(m, pd.Series([], dtype=float)), pv, higher_is_better=higher_is_better)
        rows.append({"metric": m, "pct": pct})

    pct_table = pd.DataFrame(rows)
    return pct_table, scope_label, world_pos_df, league_pos_df


def _make_exec_summary(pct_table: pd.DataFrame, top_n=3, bottom_n=3):
    if pct_table is None or pct_table.empty:
        return dbc.Alert("Sem percentis para gerar resumo executivo.", color="warning")

    tmp = pct_table.copy()
    tmp["pct_num"] = pd.to_numeric(tmp["pct"], errors="coerce")
    tmp = tmp.dropna(subset=["pct_num"])
    if tmp.empty:
        return dbc.Alert("Sem percentis válidos para gerar resumo executivo.", color="warning")

    best = tmp.sort_values("pct_num", ascending=False).head(top_n)[["metric", "pct_num"]].values.tolist()
    worst = tmp.sort_values("pct_num", ascending=True).head(bottom_n)[["metric", "pct_num"]].values.tolist()

    def bullet(metric, pct):
        return html.Li(
            [
                html.Span(metric, className="fw-semibold"),
                html.Span(f" — {pct:.0f}", style={"color": _pct_color(pct)}, className="ms-1 fw-bold"),
            ]
        )

    return dbc.Row(
        [
            dbc.Col(
                dbc.Card(dbc.CardBody([html.H6("Pontos fortes (top percentis)", className="mb-2"),
                                       html.Ul([bullet(m, p) for m, p in best], className="mb-0")])),
                md=6,
            ),
            dbc.Col(
                dbc.Card(dbc.CardBody([html.H6("Pontos a melhorar (bottom percentis)", className="mb-2"),
                                       html.Ul([bullet(m, p) for m, p in worst], className="mb-0")])),
                md=6,
            ),
        ],
        className="g-3",
    )


def _role_fit_table(player_row: pd.Series, fallback_df: pd.DataFrame):
    axis_opts = _axis_options(df)
    rows = []

    for role, preset in ROLE_PRESETS.items():
        feats = [m for m in preset if m in axis_opts]
        if len(feats) < 3:
            continue

        role_df = df[_pos_mask_for(role, df)].copy()
        if role_df.empty:
            role_df = fallback_df if (fallback_df is not None and not fallback_df.empty) else df

        vals = []
        used = 0
        for m in feats:
            pv = _safe_float(player_row.get(m, np.nan))
            if np.isnan(pv):
                continue
            s = role_df.get(m, pd.Series([], dtype=float))
            score = _minmax_scale_series(s, pv)
            if m in LOWER_IS_BETTER and not (score is None or (isinstance(score, float) and np.isnan(score))):
                score = 100.0 - float(score)
            if score is None or (isinstance(score, float) and np.isnan(score)):
                continue
            vals.append(float(score))
            used += 1

        if used < 3:
            continue

        role_score = float(np.mean(vals)) if vals else np.nan
        rows.append({"role": role, "role_label": _pos_pt(role), "score": role_score, "metrics_used": used})

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values(["score", "metrics_used"], ascending=[False, False]).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def _percentile_bar_fig(pct_table: pd.DataFrame, title: str, order: str):
    fig = go.Figure()
    fig.update_layout(template="plotly_white", height=420, title=title)

    if pct_table is None or pct_table.empty:
        return fig

    tmp = pct_table.copy()
    if order == "desc":
        tmp["_sort"] = pd.to_numeric(tmp["pct"], errors="coerce").fillna(-1)
        tmp = tmp.sort_values(["_sort", "metric"], ascending=[False, True]).drop(columns=["_sort"])
    else:
        tmp = tmp.sort_values("metric", ascending=True)

    metrics = tmp["metric"].tolist()[::-1]
    pcts = tmp["pct"].tolist()[::-1]
    colors = [_pct_color(v) for v in pcts]
    text = [("" if (v is None or (isinstance(v, float) and np.isnan(v))) else f"{v:.0f}") for v in pcts]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pcts, y=metrics, orientation="h",
        marker=dict(color=colors),
        text=text, textposition="outside",
        hovertemplate="<b>%{y}</b><br>Percentil: %{x:.0f}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        height=max(460, 28 * len(metrics) + 160),
        margin=dict(l=10, r=30, t=60, b=20),
        title=title,
        xaxis=dict(range=[0, 100], title="Percentil (melhor que X%)"),
        yaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def _radar_fig_three_traces(player_row: pd.Series, name: str, pos_label: str, radar_feats: list[str], league_pos_df: pd.DataFrame, world_pos_df: pd.DataFrame):
    player_raw = {f: _safe_float(player_row.get(f, np.nan)) for f in radar_feats}

    league_pos_mean, world_pos_mean = {}, {}
    for f in radar_feats:
        s_lp = pd.to_numeric(league_pos_df.get(f, pd.Series([], dtype=float)), errors="coerce")
        s_wp = pd.to_numeric(world_pos_df.get(f, pd.Series([], dtype=float)), errors="coerce")
        league_pos_mean[f] = float(np.nanmean(s_lp)) if len(s_lp) else np.nan
        world_pos_mean[f] = float(np.nanmean(s_wp)) if len(s_wp) else np.nan

    player_scaled, league_scaled, world_scaled = [], [], []
    for f in radar_feats:
        s_ctx = pd.to_numeric(league_pos_df.get(f, pd.Series([], dtype=float)), errors="coerce")
        if s_ctx.dropna().empty:
            s_ctx = pd.to_numeric(world_pos_df.get(f, pd.Series([], dtype=float)), errors="coerce")
        if s_ctx.dropna().empty:
            s_ctx = pd.to_numeric(df.get(f, pd.Series([], dtype=float)), errors="coerce")

        pv = player_raw.get(f, np.nan)
        lv = league_pos_mean.get(f, np.nan)
        wv = world_pos_mean.get(f, np.nan)

        player_scaled.append(_minmax_scale_series(s_ctx, pv) if not np.isnan(pv) else np.nan)
        league_scaled.append(_minmax_scale_series(s_ctx, lv) if not np.isnan(_safe_float(lv)) else np.nan)
        world_scaled.append(_minmax_scale_series(s_ctx, wv) if not np.isnan(_safe_float(wv)) else np.nan)

    cats = radar_feats + [radar_feats[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=player_scaled + [player_scaled[0]],
        theta=cats,
        fill="toself",
        name="Jogador",
        customdata=np.array([player_raw.get(f, np.nan) for f in radar_feats] + [player_raw.get(radar_feats[0], np.nan)], dtype=float),
        hovertemplate="<b>Jogador</b><br>Métrica: %{theta}<br>Norm: %{r:.1f}<br>Real: %{customdata:.4g}<extra></extra>",
    ))
    fig.add_trace(go.Scatterpolar(
        r=league_scaled + [league_scaled[0]],
        theta=cats,
        fill=None,
        name="Média da Posição (na Liga)",
        customdata=np.array([league_pos_mean.get(f, np.nan) for f in radar_feats] + [league_pos_mean.get(radar_feats[0], np.nan)], dtype=float),
        line=dict(dash="dash", width=2),
        hovertemplate="<b>Média Posição (Liga)</b><br>Métrica: %{theta}<br>Norm: %{r:.1f}<br>Real: %{customdata:.4g}<extra></extra>",
    ))
    fig.add_trace(go.Scatterpolar(
        r=world_scaled + [world_scaled[0]],
        theta=cats,
        fill=None,
        name="Média da Posição (Mundo)",
        customdata=np.array([world_pos_mean.get(f, np.nan) for f in radar_feats] + [world_pos_mean.get(radar_feats[0], np.nan)], dtype=float),
        line=dict(dash="dot", width=2),
        hovertemplate="<b>Média Posição (Mundo)</b><br>Métrica: %{theta}<br>Norm: %{r:.1f}<br>Real: %{customdata:.4g}<extra></extra>",
    ))

    fig.update_layout(
        template="plotly_white",
        height=540,
        margin=dict(l=10, r=200, t=60, b=10),
        title=f"Radar — {name} (posição usada: {pos_label})",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False)),
        legend=dict(orientation="v", x=1.02, y=0.5, xanchor="left", yanchor="middle"),
    )
    info = f"Eixos: {len(radar_feats)} | Posição do universo: {pos_label}"
    return fig, info


def _stats_table_data(player_row: pd.Series, feats: list[str], league_pos_df: pd.DataFrame, world_pos_df: pd.DataFrame, pct_table: pd.DataFrame):
    if not feats:
        return []

    pct_map = {}
    if pct_table is not None and not pct_table.empty:
        for _, rr in pct_table.iterrows():
            pct_map[str(rr.get("metric"))] = rr.get("pct")

    rows = []
    for m in feats:
        pv = _safe_float(player_row.get(m, np.nan))

        lp = pd.to_numeric(league_pos_df.get(m, pd.Series([], dtype=float)), errors="coerce")
        wp = pd.to_numeric(world_pos_df.get(m, pd.Series([], dtype=float)), errors="coerce")

        league_avg = float(np.nanmean(lp)) if len(lp) else np.nan
        world_avg = float(np.nanmean(wp)) if len(wp) else np.nan

        pct = pct_map.get(m, np.nan)
        z = np.nan
        if len(wp.dropna()) > 2 and not np.isnan(pv):
            mu = float(np.nanmean(wp))
            sd = float(np.nanstd(wp))
            if sd > 0:
                z = (pv - mu) / sd

        rows.append({
            "metric": m,
            "player": _fmt_num(pv),
            "league_avg": _fmt_num(league_avg),
            "world_avg": _fmt_num(world_avg),
            "pct": ("" if (pct is None or (isinstance(pct, float) and np.isnan(pct))) else f"{float(pct):.0f}"),
            "z_world": ("" if (np.isnan(z)) else f"{z:.2f}"),
        })

    return rows


def _norm_channel(s: str) -> str:
    return str(s or "").strip().lower()


def _priority_rank(channel_title: str) -> int:
    ch = _norm_channel(channel_title)
    for i, want in enumerate(PRIORITY_CHANNELS):
        if ch == want:
            return i
    return 999999


def _choose_main_video(items: list[dict]) -> dict | None:
    if not items:
        return None
    best = None
    best_rank = 999999
    for it in items:
        r = _priority_rank(it.get("channelTitle", ""))
        if r < best_rank:
            best_rank = r
            best = it
    return best if best is not None else items[0]


# =========================
# ✅ YouTube Search (método melhor) + cache
# =========================
def _youtube_search(query: str, max_results: int = 10) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []

    cache_key = q.lower()
    now = time.time()
    cached = _YT_CACHE.get(cache_key)
    if cached and (now - float(cached.get("ts", 0))) < _YT_CACHE_TTL_SEC:
        return (cached.get("items", []) or [])[:max_results]

    if not YOUTUBE_API_KEY:
        return []

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
        "q": q,
        "type": "video",
        "order": "relevance",
        "videoDuration": "medium",   # ✅ melhor que "short" para highlights
        "safeSearch": "strict",
        "maxResults": min(25, max(1, int(max_results))),
    }

    try:
        resp = requests.get(url, params=params, timeout=_YT_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    items = []
    for it in (data.get("items") or []):
        vid = ((it.get("id") or {}).get("videoId") or "").strip()
        sn = (it.get("snippet") or {})
        title = (sn.get("title") or "").strip()
        channel = (sn.get("channelTitle") or "").strip()
        published = (sn.get("publishedAt") or "").strip()
        if vid:
            items.append({"videoId": vid, "title": title, "channelTitle": channel, "publishedAt": published})

    _YT_CACHE[cache_key] = {"ts": now, "items": items}
    return items[:max_results]


def _youtube_embed_grid(items: list[dict], search_url: str):
    if not items:
        return dbc.Alert(
            [
                html.Div("Não encontrei vídeos automaticamente (ou a API Key não está configurada).", className="fw-semibold"),
                html.Div(
                    ["Você pode definir ", html.Code("YOUTUBE_API_KEY"), " no .env e garantir que ele está sendo carregado (python-dotenv)."],
                    className="small text-muted mt-1",
                ),
                html.Div(dbc.Button("Abrir busca no YouTube", href=search_url, target="_blank", color="primary", size="sm"), className="mt-2"),
            ],
            color="warning",
        )

    # ✅ Principal por prioridade de canal
    main = _choose_main_video(items) or items[0]
    main_id = main.get("videoId")
    rest = [it for it in items if it.get("videoId") != main_id][:7]

    # ✅ Dash 3.3.0: NÃO existe allowFullScreen no html.Iframe
    def iframe(vid, height=315):
        return html.Iframe(
            src=f"https://www.youtube.com/embed/{vid}",
            style={"width": "100%", "height": f"{height}px", "border": "0", "borderRadius": "14px"},
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen",
        )

    main_card = dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.Div("Vídeo principal (prioridade de canal)", className="text-muted small"),
                        html.Div(main.get("title", "Highlights"), className="fw-semibold"),
                    ],
                    className="mb-2",
                ),
                iframe(main_id, height=420),
                html.Div(f"Canal: {main.get('channelTitle','')}", className="small text-muted mt-2"),
            ]
        ),
        style={"borderRadius": "16px"},
        className="h-100",
    )

    thumbs = []
    for it in rest:
        vid = it.get("videoId")
        if not vid:
            continue
        thumbs.append(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div(it.get("title", ""), className="small fw-semibold mb-2", style={"minHeight": "44px"}),
                            iframe(vid, height=200),
                            html.Div(f"Canal: {it.get('channelTitle','')}", className="small text-muted mt-2"),
                        ]
                    ),
                    style={"borderRadius": "16px"},
                    className="h-100",
                ),
                md=4,
            )
        )

    return html.Div(
        [
            dbc.Row([dbc.Col(main_card, md=12)], className="g-3"),
            dbc.Row(thumbs, className="g-3 mt-1") if thumbs else None,
            html.Div(
                dbc.Button("Abrir mais resultados no YouTube", href=search_url, target="_blank", color="secondary", size="sm"),
                className="mt-3",
            ),
        ]
    )


# =========================
# Transfermarkt: Rumours scraping
# =========================
def _tm_sleep():
    time.sleep(_TM_SLEEP_SEC)


def _tm_abs_url(href: str) -> str:
    if not href:
        return ""
    h = href.strip()
    if h.startswith("http"):
        return h
    return TM_BASE_URL + h


def _tm_search_player_profile_url(player_name: str) -> str | None:
    """
    Busca pelo schnellsuche e retorna URL do perfil (player).
    """
    q = urllib.parse.quote_plus((player_name or "").strip())
    if not q:
        return None

    url = f"{TM_BASE_URL}/schnellsuche/ergebnis/schnellsuche?query={q}"

    try:
        r = _TM_SESSION.get(url, timeout=_TM_TIMEOUT)
        _tm_sleep()
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
    except Exception:
        return None

    a = soup.select_one("table.items tbody tr td.hauptlink a")
    if not a or not a.get("href"):
        return None

    return _tm_abs_url(a["href"])


def _tm_to_rumours_url(profile_url: str) -> str:
    return re.sub(r"/profil/", "/geruechte/", profile_url or "")

def _upgrade_club_logo(url: str) -> str:
    if not url:
        return ""
    return url.replace("/tiny/", "/head/")

def _tm_get_rumours_for_player(player_name: str) -> pd.DataFrame:
    """
    Cacheia por player_name (12h) e retorna DataFrame com:
    interested_club, club_url, club_logo_url, most_recent_source_date/url,
    last_reply_date/url, probability_percent, thread_title, rumours_url
    """
    key = (player_name or "").strip().lower()
    if not key:
        return pd.DataFrame()

    now = time.time()
    cached = _TM_CACHE.get(key)
    if cached and (now - float(cached.get("ts", 0))) < _TM_CACHE_TTL_SEC:
        return cached.get("df", pd.DataFrame()).copy()

    profile = _tm_search_player_profile_url(player_name)
    if not profile:
        df_out = pd.DataFrame()
        _TM_CACHE[key] = {"ts": now, "df": df_out}
        return df_out

    rumours_url = _tm_to_rumours_url(profile)

    try:
        r = _TM_SESSION.get(rumours_url, timeout=_TM_TIMEOUT)
        _tm_sleep()
        if r.status_code != 200:
            df_out = pd.DataFrame()
            _TM_CACHE[key] = {"ts": now, "df": df_out}
            return df_out
        soup = BeautifulSoup(r.text, "lxml")
    except Exception:
        df_out = pd.DataFrame()
        _TM_CACHE[key] = {"ts": now, "df": df_out}
        return df_out

    table = soup.select_one("div.box table.items")
    if not table:
        df_out = pd.DataFrame()
        _TM_CACHE[key] = {"ts": now, "df": df_out}
        return df_out

    out = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        # Logo do clube (td 0)
        logo_img = tds[0].select_one("img")
        club_logo_raw = logo_img["src"] if logo_img and logo_img.get("src") else ""
        club_logo_url = _upgrade_club_logo(club_logo_raw)
        

        # Clube interessado (td 1)
        club_a = tds[1].select_one("a")
        interested_club = club_a.get_text(strip=True) if club_a else tds[1].get_text(strip=True)
        club_url = _tm_abs_url(club_a.get("href")) if (club_a and club_a.get("href")) else ""

        # Most recent source (td 2)
        src_a = tds[2].select_one("a")
        most_recent_source_date = src_a.get_text(strip=True) if src_a else tds[2].get_text(strip=True)
        most_recent_source_url = _tm_abs_url(src_a.get("href")) if (src_a and src_a.get("href")) else ""
        thread_title_src = (src_a.get("title") or "").strip() if src_a else ""

        # Last reply (td 3)
        reply_a = tds[3].select_one("a")
        last_reply_date = reply_a.get_text(strip=True) if reply_a else tds[3].get_text(strip=True)
        last_reply_url = _tm_abs_url(reply_a.get("href")) if (reply_a and reply_a.get("href")) else ""
        thread_title_reply = (reply_a.get("title") or "").strip() if reply_a else ""

        # Probability (td 4)
        prob_text = tds[4].get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*%", prob_text)
        probability_percent = int(m.group(1)) if m else None

        prob_thread_a = tds[4].select_one("a[title][href]")
        probability_thread_url = _tm_abs_url(prob_thread_a.get("href")) if (prob_thread_a and prob_thread_a.get("href")) else ""
        thread_title_prob = (prob_thread_a.get("title") or "").strip() if prob_thread_a else ""

        thread_title = thread_title_prob or thread_title_reply or thread_title_src

        out.append({
            "interested_club": interested_club,
            "club_url": club_url,
            "club_logo_url": club_logo_url,
            "most_recent_source_date": most_recent_source_date,
            "most_recent_source_url": most_recent_source_url,
            "last_reply_date": last_reply_date,
            "last_reply_url": last_reply_url,
            "probability_percent": probability_percent,
            "thread_title": thread_title,
            "probability_thread_url": probability_thread_url,
            "rumours_url": rumours_url,
            "profile_url": profile,
        })

    df_out = pd.DataFrame(out)
    _TM_CACHE[key] = {"ts": now, "df": df_out}
    return df_out.copy()


def _badge_color_for_prob(p: int | None) -> str:
    if p is None:
        return "secondary"
    if p >= 70:
        return "success"
    if p >= 40:
        return "primary"
    if p >= 20:
        return "warning"
    return "danger"


def _rumour_card(row: dict):
    club = (row.get("interested_club") or "Clube").strip()
    logo = (row.get("club_logo_url") or "").strip()
    club_url = (row.get("club_url") or "").strip()

    prob = row.get("probability", None)  # ou a chave que você usa
    try:
        prob_f = float(prob) if prob is not None else None
    except Exception:
        prob_f = None

    prob_txt = "NA" if (prob_f is None or (isinstance(prob_f, float) and np.isnan(prob_f))) else f"{int(round(prob_f))}%"

    title = (row.get("thread_title") or "Rumour").strip()

    src_date = (row.get("most_recent_source_date") or "").strip()
    src_url = (row.get("most_recent_source_url") or "").strip()

    reply_date = (row.get("last_reply_date") or "").strip()
    reply_url = (row.get("last_reply_url") or "").strip()

    thread_url = (row.get("probability_thread_url") or src_url or reply_url or "").strip()

    logo_box = html.Img(
        src=logo,
        style={"width": "42px", "height": "42px", "objectFit": "contain"},
        alt="club",
        referrerPolicy="no-referrer",
        crossOrigin="anonymous",
    ) if logo else html.Div(style={"width": "42px", "height": "42px", "borderRadius": "10px", "backgroundColor": "rgba(0,0,0,0.06)"})

    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(logo_box, width="auto"),
                        dbc.Col(
                            [
                                html.Div(
                                    [
                                        html.Span(club, className="fw-bold"),
                                        (html.Span(" • ", className="text-muted") if club_url else None),
                                        (html.A("ver clube", href=club_url, target="_blank", className="small") if club_url else None),
                                    ],
                                    className="mb-1",
                                ),
                                html.Div(title, className="text-muted small", style={"lineHeight": "16px"}),
                            ]
                        ),
                        dbc.Col(
                            dbc.Badge(
                                ["Probabilidade ", html.Span(prob_txt, className="fw-bold")],
                                color=_badge_color_for_prob(prob),
                                pill=True,
                                className="ms-auto",
                                style={"fontSize": "12px", "padding": "8px 10px"},
                            ),
                            width="auto",
                        ),
                    ],
                    className="g-2 align-items-center",
                ),
                html.Hr(className="my-3"),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div("Most recent source", className="text-muted", style={"fontSize": "12px"}),
                                        html.Div(
                                            html.A(src_date or "NA", href=src_url, target="_blank", className="fw-semibold")
                                            if src_url else html.Span(src_date or "NA", className="fw-semibold"),
                                            style={"fontSize": "14px"},
                                        ),
                                    ],
                                    className="py-2",
                                ),
                                style={"borderRadius": "14px"},
                            ),
                            md=6,
                        ),
                        dbc.Col(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div("Last reply", className="text-muted", style={"fontSize": "12px"}),
                                        html.Div(
                                            html.A(reply_date or "NA", href=reply_url, target="_blank", className="fw-semibold")
                                            if reply_url else html.Span(reply_date or "NA", className="fw-semibold"),
                                            style={"fontSize": "14px"},
                                        ),
                                    ],
                                    className="py-2",
                                ),
                                style={"borderRadius": "14px"},
                            ),
                            md=6,
                        ),
                    ],
                    className="g-2",
                ),
                html.Div(
                    dbc.Button("Abrir thread", href=thread_url, target="_blank", color="secondary", size="sm")
                    if thread_url else None,
                    className="mt-3",
                ),
            ]
        ),
        style={"borderRadius": "16px"},
        className="h-100",
    )


def _rumours_view(player_name: str):
    df_r = _tm_get_rumours_for_player(player_name)

    if df_r is None or df_r.empty:
        search_url = f"{TM_BASE_URL}/schnellsuche/ergebnis/schnellsuche?query={urllib.parse.quote_plus((player_name or '').strip())}"
        return dbc.Alert(
            [
                html.Div("Sem rumores abertos encontrados para este jogador (ou não consegui carregar a tabela).", className="fw-semibold"),
                html.Div("Dica: alguns jogadores simplesmente não têm rumores abertos no Transfermarkt.", className="text-muted small mt-1"),
                html.Div(
                    dbc.Button("Abrir busca no Transfermarkt", href=search_url, target="_blank", color="primary", size="sm"),
                    className="mt-2",
                ),
            ],
            color="warning",
        )

    # Ordena por probabilidade desc e depois por data recente (string; mantém simples)
    tmp = df_r.copy()
    tmp["probability_percent_num"] = pd.to_numeric(tmp["probability_percent"], errors="coerce").fillna(-1)
    tmp = tmp.sort_values(["probability_percent_num"], ascending=False).drop(columns=["probability_percent_num"])

    # KPIs do bloco
    probs = pd.to_numeric(tmp["probability_percent"], errors="coerce").dropna()
    cards = []
    cards.append(_kpi_card("Rumores", str(int(len(tmp)))))
    cards.append(_kpi_card("Prob. média", (f"{float(probs.mean()):.0f}%" if not probs.empty else "NA")))
    cards.append(_kpi_card("Prob. máx", (f"{float(probs.max()):.0f}%" if not probs.empty else "NA")))
    cards.append(_kpi_card("Prob. mín", (f"{float(probs.min()):.0f}%" if not probs.empty else "NA")))

    cols = []
    for _, rr in tmp.head(12).iterrows():
        cols.append(dbc.Col(_rumour_card(rr.to_dict()), md=6, lg=4))

    footer_links = tmp.iloc[0].to_dict()
    rumours_url = (footer_links.get("rumours_url") or "").strip()
    profile_url = (footer_links.get("profile_url") or "").strip()

    return html.Div(
        [
            dbc.Row(cards, className="g-2"),
            html.Hr(className="my-3"),
            dbc.Row(cols, className="g-3"),
            html.Div(
                [
                    dbc.Button("Abrir página de rumores (Transfermarkt)", href=rumours_url, target="_blank", color="secondary", size="sm", className="me-2") if rumours_url else None,
                    dbc.Button("Abrir perfil (Transfermarkt)", href=profile_url, target="_blank", color="secondary", size="sm") if profile_url else None,
                ],
                className="mt-3",
            ),
            html.Div("Obs: esta aba faz scraping — pode falhar se o site mudar o HTML ou bloquear muitas requisições.", className="text-muted small mt-2"),
        ]
    )


# =========================
# Layout
# =========================
role_options = [{"label": _pos_pt(k), "value": k} for k in ROLE_PRESETS.keys()]

layout = dbc.Container(
    fluid=True,
    style={"maxWidth": "100%", "paddingLeft": "12px", "paddingRight": "12px"},
    children=[
        dcc.Location(id="player_url"),
        dcc.Store(id="player_ctx_store"),
        dcc.Store(id="player_active_tab", data="overview"),

        html.Div(id="player_header"),

        dbc.Card(
            dbc.CardBody(
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Posição (preset do radar)", className="fw-semibold"),
                                dcc.Dropdown(
                                    id="radar_role_dd",
                                    options=role_options,
                                    value=None,
                                    clearable=False,
                                    placeholder="Selecione a posição…",
                                ),
                                html.Div(
                                    "Ao mudar a posição, o seletor de métricas do radar é preenchido com o preset.",
                                    className="text-muted small mt-1",
                                ),
                            ],
                            md=5,
                        ),
                        dbc.Col(
                            [
                                html.Label("Métricas do radar (você pode adicionar/remover)", className="fw-semibold"),
                                dcc.Dropdown(
                                    id="radar_metrics_dd",
                                    options=[],
                                    value=[],
                                    multi=True,
                                    placeholder="Selecione métricas…",
                                ),
                            ],
                            md=7,
                        ),
                    ],
                    className="g-3",
                )
            ),
            className="mt-2",
            style={"borderRadius": "16px"},
        ),

        # ✅ Tabs como Buttons (não mexe no scroll)
        dbc.Card(
            dbc.CardBody(
                html.Div(
                    dbc.ButtonGroup(
                        [
                            dbc.Button("Visão geral", id="tab_overview_btn", n_clicks=0, className="player-tab-btn"),
                            dbc.Button("Percentis", id="tab_percentis_btn", n_clicks=0, className="player-tab-btn"),
                            dbc.Button("Comparáveis", id="tab_comparaveis_btn", n_clicks=0, className="player-tab-btn"),
                            dbc.Button("Estatísticas", id="tab_stats_btn", n_clicks=0, className="player-tab-btn"),
                            dbc.Button("Highlights", id="tab_highlights_btn", n_clicks=0, className="player-tab-btn"),
                            dbc.Button("Rumores", id="tab_rumores_btn", n_clicks=0, className="player-tab-btn"),
                        ],
                        className="player-tabs-group"
                    ),
                    className="player-tabs-wrapper"
                )
            ),
            className="mt-3",
            style={"borderRadius": "16px"},
        ),

        html.Div(id="player_tab_content", className="mt-3 mb-4"),
    ],
)

# =========================
# Tab state (Button clicks)
# =========================
@dash.callback(
    Output("player_active_tab", "data"),
    Output("tab_overview_btn", "className"),
    Output("tab_percentis_btn", "className"),
    Output("tab_comparaveis_btn", "className"),
    Output("tab_stats_btn", "className"),
    Output("tab_highlights_btn", "className"),
    Output("tab_rumores_btn", "className"),
    Input("tab_overview_btn", "n_clicks"),
    Input("tab_percentis_btn", "n_clicks"),
    Input("tab_comparaveis_btn", "n_clicks"),
    Input("tab_stats_btn", "n_clicks"),
    Input("tab_highlights_btn", "n_clicks"),
    Input("tab_rumores_btn", "n_clicks"),
    State("player_active_tab", "data"),
    prevent_initial_call=False,
)
def set_active_tab(n1, n2, n3, n4, n5, n6, current):
    trig = dash.callback_context.triggered
    tab = current or "overview"

    if trig and trig[0].get("prop_id"):
        pid = trig[0]["prop_id"].split(".")[0]
        mapping = {
            "tab_overview_btn": "overview",
            "tab_percentis_btn": "percentis",
            "tab_comparaveis_btn": "comparaveis",
            "tab_stats_btn": "stats",
            "tab_highlights_btn": "highlights",
            "tab_rumores_btn": "rumores",
        }
        tab = mapping.get(pid, tab)

    def cls(is_active):
        return "player-tab-btn active" if is_active else "player-tab-btn"

    return (
        tab,
        cls(tab == "overview"),
        cls(tab == "percentis"),
        cls(tab == "comparaveis"),
        cls(tab == "stats"),
        cls(tab == "highlights"),
        cls(tab == "rumores"),
    )

# =========================
# 1) Carrega contexto + defaults
# =========================
@dash.callback(
    Output("player_ctx_store", "data"),
    Output("radar_role_dd", "value"),
    Output("radar_metrics_dd", "options"),
    Input("player_url", "pathname"),
)
def load_player_ctx_and_defaults(pathname: str):
    if not pathname:
        return None, None, []

    parts = [p for p in pathname.split("/") if p]
    if len(parts) < 2:
        return None, None, []

    playerid = parts[-1]
    r = _get_player_row(playerid)
    if r is None:
        return {"error": "Jogador não encontrado"}, None, []

    league = r.get("leaguename", None)
    pos_player = _get_pos_code_main(r)
    role_default = pos_player if pos_player in ROLE_PRESETS else "ST"

    axis_opts = _axis_options(df)
    all_opts = [{"label": c, "value": c} for c in axis_opts]

    preferred_pct = [
        "rating", "minutesplayed", "appearances",
        "goals", "assists", "expectedgoals", "expectedassists", "xg", "xa",
        "totalshots", "shotsontarget",
        "keypasses", "chancescreated", "bigchancescreated",
        "totalpasses", "accuratepassespercentage", "passaccuracy",
        "tackles", "interceptions",
        "successfuldribbles",
    ]
    pct_default = [m for m in preferred_pct if m in axis_opts]
    if len(pct_default) < 6:
        pct_default = [m for m in DEFAULT_PRESET if m in axis_opts]

    return (
        {"playerid": _to_int_safe(playerid), "league": (league if pd.notna(league) else None), "pos_player": pos_player, "pct_default": pct_default},
        role_default,
        all_opts,
    )

# =========================
# 2) Ao mudar a posição, preenche o radar_metrics_dd com o preset
# =========================
@dash.callback(
    Output("radar_metrics_dd", "value"),
    Input("radar_role_dd", "value"),
    State("radar_metrics_dd", "options"),
)
def fill_radar_metrics_from_role(role, options):
    if not role:
        return []
    opt_set = set([o["value"] for o in (options or [])])

    preset = ROLE_PRESETS.get(role, DEFAULT_PRESET)
    preset = [m for m in preset if m in opt_set]

    if len(preset) < 3:
        preset = [m for m in DEFAULT_PRESET if m in opt_set]

    return preset[:8]

# =========================
# 3) Render header + tab content
# =========================
@dash.callback(
    Output("player_header", "children"),
    Output("player_tab_content", "children"),
    Input("player_url", "pathname"),
    Input("player_active_tab", "data"),
    Input("radar_role_dd", "value"),
    Input("radar_metrics_dd", "value"),
    State("player_ctx_store", "data"),
)
def render_page(pathname: str, active_tab: str, role_selected, chosen_radar_metrics, ctx_store):
    if not pathname:
        header = dbc.Alert("URL inválida.", color="warning")
        return header, header

    parts = [p for p in pathname.split("/") if p]
    if len(parts) < 2:
        header = dbc.Alert("playerid não informado.", color="warning")
        return header, header

    playerid = parts[-1]
    r = _get_player_row(playerid)
    if r is None:
        header = dbc.Alert("Jogador não encontrado no dataset atual.", color="danger")
        return header, header

    name = r.get("playername", "NA")
    team = r.get("teamname", "NA")
    league = r.get("leaguename", "NA")
    country = r.get("country", r.get("playercountry", "NA")) if ("country" in r.index or "playercountry" in r.index) else "NA"
    age = _fmt_num(r.get("age", np.nan))
    minutes = _fmt_num(r.get("minutesplayed", np.nan))
    img = (r.get("photo_url", "") or "").strip()
    sofascore = (r.get("sofascore_url", "") or "").strip()

    pos_code = role_selected or _get_pos_code_main(r)
    pos_label = _pos_pt(pos_code)

    pos_mask = _pos_mask_for(pos_code, df)
    league_mask = _league_mask_for(league, df)
    world_pos_df = df[pos_mask].copy()
    league_pos_df = df[pos_mask & league_mask].copy()

    kpi_cols = [
        ("Rating", "rating"),
        ("Minutos", "minutesplayed"),
        ("Gols", "goals"),
        ("Assists", "assists"),
        ("Jogos", "appearances"),
        ("xG", "xg" if "xg" in r.index else "expectedgoals"),
        ("xA", "xa" if "xa" in r.index else "expectedassists"),
    ]
    kpi_cards = []
    for lbl, col in kpi_cols:
        if col in r.index:
            kpi_cards.append(_kpi_card(lbl, _fmt_num(r.get(col, np.nan))))
    kpi_cards = kpi_cards[:8]

    img_style_big = {"width": "120px", "height": "120px", "borderRadius": "16px", "objectFit": "cover", "backgroundColor": "rgba(0,0,0,0.06)"}

    header = dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Img(
                                        src=img,
                                        style=img_style_big,
                                        referrerPolicy="no-referrer",
                                        crossOrigin="anonymous",
                                        alt="player",
                                    )
                                    if img
                                    else html.Div(style=img_style_big),
                                    width="auto",
                                ),
                                dbc.Col(
                                    [
                                        html.H3(name, className="mb-0"),
                                        html.Div(f"{team} • {league}", className="text-muted"),
                                        html.Div(f"{pos_label} • {country} • {age} anos", className="text-muted"),
                                        html.Div(f"Minutos: {minutes}", className="text-muted"),
                                        html.Div(f"PlayerID: {playerid}", className="text-muted small"),
                                        html.Hr(),
                                        dbc.Row(kpi_cards, className="g-2"),
                                        html.Div(
                                            dbc.Button("Abrir no SofaScore", href=sofascore, target="_blank", color="primary", size="sm")
                                            if sofascore
                                            else None,
                                            className="mt-2",
                                        ),
                                    ]
                                ),
                            ],
                            className="g-3 align-items-center",
                        )
                    ),
                    style={"borderRadius": "16px"},
                ),
                md=12,
            )
        ],
        className="g-3 mt-2",
    )

    axis_opts = _axis_options(df)
    radar_feats = [m for m in (chosen_radar_metrics or []) if m in df.columns]
    if len(radar_feats) < 3:
        radar_feats = _only_existing_metrics(ROLE_PRESETS.get(pos_code, DEFAULT_PRESET), df)[:8]
        if len(radar_feats) < 3:
            radar_feats = _only_existing_metrics(DEFAULT_PRESET, df)[:8]

    if active_tab == "overview":
        pct_default = (ctx_store or {}).get("pct_default", [])
        pct_feats = [m for m in pct_default if m in axis_opts]
        if len(pct_feats) < 6:
            pct_feats = [m for m in DEFAULT_PRESET if m in axis_opts]

        pct_table, scope_label, _, _ = _compute_percentile_table(
            player_row=r,
            pos_code=pos_code,
            league=league,
            pct_feats=pct_feats,
            scope="league_pos",
        )

        radar_fig, radar_info = _radar_fig_three_traces(
            player_row=r,
            name=name,
            pos_label=pos_label,
            radar_feats=radar_feats,
            league_pos_df=(league_pos_df if not league_pos_df.empty else world_pos_df),
            world_pos_df=(world_pos_df if not world_pos_df.empty else df),
        )

        role_fit_df = _role_fit_table(r, (world_pos_df if not world_pos_df.empty else df))
        if role_fit_df.empty:
            role_fit_block = dbc.Alert("Não foi possível calcular Role Fit (dados insuficientes).", color="warning")
        else:
            top3 = role_fit_df.head(3)
            chips = []
            for _, rr in top3.iterrows():
                chips.append(
                    dbc.Badge(
                        f"{int(rr['rank'])}º {rr['role_label']} — {rr['score']:.0f}",
                        color="secondary",
                        className="me-2 mb-2",
                        pill=True,
                    )
                )
            role_fit_block = dbc.Card(
                dbc.CardBody(
                    [
                        html.H5("Role Fit (encaixe por papel)", className="mb-1"),
                        html.Div("Score = média das métricas do preset (normalizadas).", className="text-muted small"),
                        html.Div(chips, className="mt-2"),
                        dbc.Button("Ver tabela completa (aba Estatísticas)", id="go_stats_btn", color="link", size="sm", style={"paddingLeft": "0"}),
                    ]
                ),
                style={"borderRadius": "16px"},
            )

        content = html.Div(
            [
                _make_exec_summary(pct_table, top_n=3, bottom_n=3),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.H5("Radar (Jogador vs Médias)", className="mb-2"),
                                        html.Div(radar_info, className="text-muted small mb-2"),
                                        dcc.Graph(
                                            figure=radar_fig,
                                            config={"displayModeBar": True, "displaylogo": False, "responsive": True},
                                        ),
                                    ]
                                ),
                                style={"borderRadius": "16px"},
                            ),
                            md=8,
                        ),
                        dbc.Col(role_fit_block, md=4),
                    ],
                    className="g-3 mt-3",
                ),
            ]
        )
        return header, content

    if active_tab == "percentis":
        pct_default = (ctx_store or {}).get("pct_default", [])
        default_pct_feats = [m for m in pct_default if m in axis_opts]
        if len(default_pct_feats) < 6:
            default_pct_feats = [m for m in DEFAULT_PRESET if m in axis_opts]

        content = dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Percentis do jogador", className="mb-2"),
                    html.Div("“98” = melhor que 98% no universo selecionado.", className="text-muted small"),

                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Universo de comparação", className="fw-semibold mt-2"),
                                    dbc.RadioItems(
                                        id="pct_scope",
                                        options=[
                                            {"label": "Posição na liga", "value": "league_pos"},
                                            {"label": "Posição no mundo", "value": "world_pos"},
                                        ],
                                        value="league_pos",
                                        inline=True,
                                    ),
                                ],
                                md=6,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Ordenação", className="fw-semibold mt-2"),
                                    dbc.RadioItems(
                                        id="pct_order",
                                        options=[
                                            {"label": "Alfabética", "value": "alpha"},
                                            {"label": "Maior → menor (percentil)", "value": "desc"},
                                        ],
                                        value="desc",
                                        inline=True,
                                    ),
                                ],
                                md=6,
                            ),
                        ],
                        className="g-3",
                    ),

                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Métricas do percentil", className="fw-semibold mt-2"),
                                    dcc.Dropdown(
                                        id="pct_metrics_dd",
                                        options=[{"label": c, "value": c} for c in axis_opts],
                                        value=default_pct_feats,
                                        multi=True,
                                        placeholder="Selecione métricas para percentis…",
                                    ),
                                ],
                                md=12,
                            ),
                        ],
                        className="g-3",
                    ),

                    html.Hr(className="my-3"),

                    dcc.Loading(
                        type="default",
                        children=[
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Graph(
                                        id="pct_graph_full",
                                        config={"displayModeBar": True, "displaylogo": False, "responsive": True},
                                    )
                                ),
                                style={"borderRadius": "16px"},
                            ),
                            html.Div(id="pct_grouped_area", className="mt-3"),
                        ],
                    ),
                ]
            ),
            style={"borderRadius": "16px"},
        )
        return header, content

    if active_tab == "comparaveis":
        sim_df = _similar_players(r, pos_code=pos_code, feats=radar_feats, topk=6)

        if sim_df.empty:
            sim_children = dbc.Alert("Não foi possível calcular similares (dados insuficientes).", color="warning")
        else:
            cols = []
            for _, s in sim_df.iterrows():
                sid = _to_int_safe(s.get("playerid"))
                sname = s.get("playername", "NA")
                steam = s.get("teamname", "NA")
                sleague = s.get("leaguename", "NA")
                sage = _fmt_num(s.get("age", np.nan))
                smin = _fmt_num(s.get("minutesplayed", np.nan))
                srating = _fmt_num(s.get("rating", np.nan))
                sphoto = (s.get("photo_url", "") or "").strip()

                img_style = {"width": "72px", "height": "72px", "borderRadius": "12px", "objectFit": "cover", "backgroundColor": "rgba(0,0,0,0.06)"}
                link = dcc.Link("Abrir jogador", href=(f"/jogador/{int(sid)}" if sid is not None else "#"), className="small")

                cols.append(
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                html.Img(
                                                    src=sphoto,
                                                    style=img_style,
                                                    referrerPolicy="no-referrer",
                                                    crossOrigin="anonymous",
                                                    alt="player",
                                                )
                                                if sphoto
                                                else html.Div(style=img_style),
                                                width="auto",
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Div(sname, className="fw-bold"),
                                                    html.Div(steam, className="text-muted"),
                                                    html.Div(sleague, className="text-muted small"),
                                                ]
                                            ),
                                        ],
                                        className="g-2 align-items-center",
                                    ),
                                    html.Hr(),
                                    html.Div(f"Idade: {sage}", className="small"),
                                    html.Div(f"Minutos: {smin}", className="small"),
                                    html.Div(f"Rating: {srating}", className="small fw-semibold"),
                                    html.Div(link, className="mt-2"),
                                ]
                            ),
                            style={"borderRadius": "16px"},
                        ),
                        md=4,
                    )
                )
            sim_children = dbc.Row(cols, className="g-3")

        content = dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Jogadores semelhantes", className="mb-2"),
                    html.Div("Similaridade estatística (z-score) dentro do universo da posição selecionada.", className="text-muted small"),
                    html.Div(sim_children, className="mt-3"),
                ]
            ),
            style={"borderRadius": "16px"},
        )
        return header, content

    if active_tab == "stats":
        feats = []
        for m in radar_feats:
            if m in axis_opts and m not in feats:
                feats.append(m)
        for group_metrics in PCT_GROUPS.values():
            for m in group_metrics:
                if m in axis_opts and m not in feats:
                    feats.append(m)
        feats = feats[:32]

        pct_table, scope_label, world_pos_df2, league_pos_df2 = _compute_percentile_table(
            player_row=r,
            pos_code=pos_code,
            league=league,
            pct_feats=feats,
            scope="league_pos",
        )

        league_ctx = league_pos_df2 if not league_pos_df2.empty else world_pos_df2
        world_ctx = world_pos_df2 if not world_pos_df2.empty else df

        data_rows = _stats_table_data(
            player_row=r,
            feats=feats,
            league_pos_df=league_ctx,
            world_pos_df=world_ctx,
            pct_table=pct_table,
        )

        role_fit_df = _role_fit_table(r, world_ctx)
        role_fit_data = []
        if not role_fit_df.empty:
            for _, rr in role_fit_df.iterrows():
                role_fit_data.append({
                    "rank": int(rr["rank"]),
                    "role": rr["role_label"],
                    "score": ("" if np.isnan(rr["score"]) else f"{rr['score']:.0f}"),
                    "metrics_used": int(rr["metrics_used"]),
                })

        content = dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5("Tabela de métricas (jogador vs médias + percentil)", className="mb-1"),
                                html.Div(f"Percentil calculado em: {scope_label}.", className="text-muted small"),
                                dash_table.DataTable(
                                    columns=[
                                        {"name": "Métrica", "id": "metric"},
                                        {"name": "Jogador", "id": "player"},
                                        {"name": "Média Liga", "id": "league_avg"},
                                        {"name": "Média Mundo", "id": "world_avg"},
                                        {"name": "Percentil", "id": "pct"},
                                        {"name": "Z (mundo)", "id": "z_world"},
                                    ],
                                    data=data_rows,
                                    page_size=18,
                                    sort_action="native",
                                    filter_action="native",
                                    style_table={"overflowX": "auto"},
                                    style_cell={"padding": "10px", "fontFamily": "system-ui", "fontSize": "13px", "whiteSpace": "nowrap"},
                                    style_header={"fontWeight": "700"},
                                ),
                            ]
                        ),
                        style={"borderRadius": "16px"},
                    ),
                    md=8,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5("Role Fit (tabela)", className="mb-1"),
                                html.Div("Ranking de encaixe por papel (com base nos presets).", className="text-muted small"),
                                html.Hr(),
                                dash_table.DataTable(
                                    columns=[
                                        {"name": "#", "id": "rank"},
                                        {"name": "Role", "id": "role"},
                                        {"name": "Score", "id": "score"},
                                        {"name": "Métricas", "id": "metrics_used"},
                                    ],
                                    data=role_fit_data,
                                    page_size=10,
                                    sort_action="native",
                                    style_table={"overflowX": "auto"},
                                    style_cell={"padding": "10px", "fontFamily": "system-ui", "fontSize": "13px", "whiteSpace": "nowrap"},
                                    style_header={"fontWeight": "700"},
                                ),
                            ]
                        ),
                        style={"borderRadius": "16px"},
                    ),
                    md=4,
                ),
            ],
            className="g-3",
        )
        return header, content

    if active_tab == "highlights":

        content = dbc.Card(
            dbc.CardBody(
                [

                    html.H5("Highlights (YouTube)", className="mb-2"),

                    dbc.RadioItems(
                        id="video_type_selector",
                        options=[
                            {"label": "Highlights", "value": "highlights"},
                            {"label": "Goals", "value": "goals"},
                            {"label": "Skills", "value": "skills"},
                            {"label": "Scout Reports", "value": "scout"},
                        ],
                        value="highlights",
                        inline=True,
                        className="mb-3",
                    ),

                    dcc.Loading(
                        type="default",
                        children=html.Div(id="video_results_area")
                    )

                ]
            ),
            style={"borderRadius": "16px"},
        )

        return header, content

    if active_tab == "rumores":
        content = dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Rumores de transferência (Transfermarkt)", className="mb-1"),
                    html.Div("Tabela “Rumours” com clubes interessados + probabilidade + datas (cards).", className="text-muted small"),
                    html.Hr(),
                    dcc.Loading(type="default", children=_rumours_view(str(name).strip())),
                ]
            ),
            style={"borderRadius": "16px"},
        )
        return header, content

    return header, dbc.Alert("Aba inválida.", color="warning")


# =========================
# 4) Tab Percentis: gráfico + agrupados
# =========================
@dash.callback(
    Output("pct_graph_full", "figure"),
    Output("pct_grouped_area", "children"),
    Input("player_url", "pathname"),
    Input("radar_role_dd", "value"),
    Input("pct_scope", "value"),
    Input("pct_order", "value"),
    Input("pct_metrics_dd", "value"),
)
def render_percentis_tab(pathname, role_selected, pct_scope, pct_order, pct_metrics):
    fig_empty = go.Figure()
    fig_empty.update_layout(template="plotly_white", title="Percentis")

    if not pathname:
        return fig_empty, dbc.Alert("URL inválida.", color="warning")

    parts = [p for p in pathname.split("/") if p]
    if len(parts) < 2:
        return fig_empty, dbc.Alert("playerid não informado.", color="warning")

    playerid = parts[-1]
    r = _get_player_row(playerid)
    if r is None:
        return fig_empty, dbc.Alert("Jogador não encontrado.", color="danger")

    name = r.get("playername", "NA")
    league = r.get("leaguename", "NA")

    pos_code = role_selected or _get_pos_code_main(r)
    pos_label = _pos_pt(pos_code)

    axis_opts = _axis_options(df)
    pct_feats = [m for m in (pct_metrics or []) if m in axis_opts]
    if len(pct_feats) < 3:
        pct_feats = _only_existing_metrics(ROLE_PRESETS.get(pos_code, DEFAULT_PRESET), df)[:16]

    pct_table, scope_label, world_pos_df, league_pos_df = _compute_percentile_table(
        player_row=r,
        pos_code=pos_code,
        league=league,
        pct_feats=pct_feats,
        scope=("world_pos" if pct_scope == "world_pos" else "league_pos"),
    )

    full_title = f"Percentis — {name} (comparação: {scope_label}) | posição usada: {pos_label}"
    fig_full = _percentile_bar_fig(pct_table, title=full_title, order=(pct_order or "desc"))

    pct_map = {row["metric"]: row["pct"] for _, row in pct_table.iterrows()} if (pct_table is not None and not pct_table.empty) else {}

    league_ctx = league_pos_df if not league_pos_df.empty else world_pos_df
    world_ctx = world_pos_df if not world_pos_df.empty else df

    pcts_all = pd.to_numeric(pd.Series(list(pct_map.values())), errors="coerce").dropna()
    global_cards = []
    if not pcts_all.empty:
        global_cards.append(_kpi_card("Média (pct)", f"{float(pcts_all.mean()):.0f}"))
        global_cards.append(_kpi_card("Mediana (pct)", f"{float(pcts_all.median()):.0f}"))
        global_cards.append(_kpi_card("Métricas", str(int(len(pcts_all)))))
    else:
        global_cards.append(_kpi_card("Métricas", "0"))

    accordion_items = []
    for cat, candidates in PCT_GROUPS.items():
        metrics = [m for m in candidates if m in pct_map]
        if len(metrics) < 2:
            continue

        cat_pcts = pd.to_numeric(pd.Series([pct_map[m] for m in metrics]), errors="coerce").dropna()
        if cat_pcts.empty:
            continue

        cat_mean = float(cat_pcts.mean())
        cat_med = float(cat_pcts.median())

        best_m = metrics[int(np.nanargmax([pct_map.get(m, np.nan) for m in metrics]))]
        worst_m = metrics[int(np.nanargmin([pct_map.get(m, np.nan) for m in metrics]))]

        cat_rows = []
        for m in metrics:
            pv = _safe_float(r.get(m, np.nan))
            lp = pd.to_numeric(league_ctx.get(m, pd.Series([], dtype=float)), errors="coerce")
            wp = pd.to_numeric(world_ctx.get(m, pd.Series([], dtype=float)), errors="coerce")
            league_avg = float(np.nanmean(lp)) if len(lp) else np.nan
            world_avg = float(np.nanmean(wp)) if len(wp) else np.nan
            cat_rows.append({
                "metric": m,
                "player": _fmt_num(pv),
                "league_avg": _fmt_num(league_avg),
                "world_avg": _fmt_num(world_avg),
                "pct": ("" if (pct_map.get(m) is None or (isinstance(pct_map.get(m), float) and np.isnan(pct_map.get(m)))) else f"{float(pct_map.get(m)):.0f}"),
            })

        pcts = [pct_map[m] for m in metrics][::-1]
        mets = metrics[::-1]
        colors = [_pct_color(v) for v in pcts]
        text = [("" if (v is None or (isinstance(v, float) and np.isnan(v))) else f"{v:.0f}") for v in pcts]

        fig_cat = go.Figure()
        fig_cat.add_trace(go.Bar(
            x=pcts, y=mets, orientation="h",
            marker=dict(color=colors),
            text=text, textposition="outside",
            hovertemplate="<b>%{y}</b><br>Percentil: %{x:.0f}<extra></extra>",
        ))
        fig_cat.update_layout(
            template="plotly_white",
            height=max(260, 26 * len(mets) + 140),
            margin=dict(l=10, r=20, t=20, b=10),
            xaxis=dict(range=[0, 100], title=""),
            yaxis=dict(title=""),
            showlegend=False,
        )

        head_badges = html.Div(
            [
                dbc.Badge(f"Média: {cat_mean:.0f}", color="secondary", pill=True, className="me-2 mb-2"),
                dbc.Badge(f"Mediana: {cat_med:.0f}", color="secondary", pill=True, className="me-2 mb-2"),
                dbc.Badge(f"Top: {best_m} ({pct_map[best_m]:.0f})", color="success", pill=True, className="me-2 mb-2"),
                dbc.Badge(f"Low: {worst_m} ({pct_map[worst_m]:.0f})", color="warning", pill=True, className="mb-2"),
            ],
            className="mb-2",
        )

        accordion_items.append(
            dbc.AccordionItem(
                title=f"{cat} • média {cat_mean:.0f}",
                children=[
                    head_badges,
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Card(dbc.CardBody(dcc.Graph(figure=fig_cat, config={"displayModeBar": False, "displaylogo": False}))),
                                md=6,
                            ),
                            dbc.Col(
                                dbc.Card(
                                    dbc.CardBody(
                                        dash_table.DataTable(
                                            columns=[
                                                {"name": "Métrica", "id": "metric"},
                                                {"name": "Jogador", "id": "player"},
                                                {"name": "Média Liga", "id": "league_avg"},
                                                {"name": "Média Mundo", "id": "world_avg"},
                                                {"name": "Pct", "id": "pct"},
                                            ],
                                            data=cat_rows,
                                            page_size=8,
                                            sort_action="native",
                                            style_table={"overflowX": "auto"},
                                            style_cell={"padding": "10px", "fontFamily": "system-ui", "fontSize": "13px", "whiteSpace": "nowrap"},
                                            style_header={"fontWeight": "700"},
                                        )
                                    ),
                                    style={"borderRadius": "16px"},
                                ),
                                md=6,
                            ),
                        ],
                        className="g-3",
                    ),
                ],
            )
        )

    grouped_block = dbc.Card(
        dbc.CardBody(
            [
                html.H5("Percentis agrupados (por categoria)", className="mb-2"),
                html.Div("Médias/medianas por categoria + top/low + gráfico + tabela com valores reais.", className="text-muted small"),
                dbc.Row(global_cards, className="g-2 mt-2"),
                html.Hr(className="my-3"),
                (dbc.Accordion(accordion_items, always_open=False, flush=True) if accordion_items
                 else dbc.Alert("Não consegui formar categorias com as métricas selecionadas.", color="warning")),
            ]
        ),
        style={"borderRadius": "16px"},
        className="mt-3",
    )

    return fig_full, grouped_block

# =========================
# 5) Botão "ver tabela completa" -> muda tab para stats
# =========================
@dash.callback(
    Output("player_active_tab", "data", allow_duplicate=True),
    Input("go_stats_btn", "n_clicks"),
    State("player_active_tab", "data"),
    prevent_initial_call=True,
)
def go_to_stats(n, current):
    if not n:
        return current
    return "stats"

@dash.callback(
    Output("video_results_area", "children"),
    Input("video_type_selector", "value"),
    State("player_url", "pathname"),
)
def update_video_results(video_type, pathname):

    if not pathname:
        return dbc.Alert("URL inválida.", color="warning")

    parts = [p for p in pathname.split("/") if p]
    if len(parts) < 2:
        return dbc.Alert("PlayerID inválido.", color="warning")

    playerid = parts[-1]
    r = _get_player_row(playerid)

    if r is None:
        return dbc.Alert("Jogador não encontrado.", color="danger")

    name = str(r.get("playername", "")).strip()
    teamName = str(r.get("teamname", "")).strip()
    if video_type == "goals":
        query = f"{name} {teamName} goals"

    elif video_type == "skills":
        query = f"{name} {teamName} skills"

    elif video_type == "scout":
        query = f"{name} {teamName} scout report"

    else:
        query = f"{name} highlights {teamName}"

    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)

    items = _youtube_search(query, max_results=_YT_MAX_RESULTS)

    return _youtube_embed_grid(items, search_url)