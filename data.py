import ast
import numpy as np
import pandas as pd
import re
import unicodedata

CSV_PATH = "stats.csv"


def _safe_parse_list(x):
    if pd.isna(x):
        return []
    if isinstance(x, list):
        return x
    try:
        v = ast.literal_eval(x)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def slugify_name(name: str) -> str:
    s = str(name).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s


def sofascore_player_url(playername: str, playerid) -> str:
    if pd.isna(playername) or pd.isna(playerid):
        return ""
    try:
        pid = int(float(playerid))
    except Exception:
        return ""
    return f"https://www.sofascore.com/pt/football/player/{slugify_name(playername)}/{pid}"


# =========================
# POSITIONS: PT DISPLAY
# =========================
POS_PT = {
    "GK": "Goleiro",
    "DC": "Zagueiro",
    "DL": "Lateral Esquerdo",
    "DR": "Lateral Direito",
    "DM": "Volante",
    "MC": "Meio-campista Central",
    "ML": "Meia Esquerda",
    "MR": "Meia Direita",
    "AM": "Meia Atacante",
    "LW": "Ponta Esquerda",
    "RW": "Ponta Direita",
    "ST": "Centroavante",
}

POSITION_ORDER = ["GK", "DC", "DL", "DR", "DM", "MC", "ML", "MR", "AM", "LW", "RW", "ST"]


def pos_to_pt(code: str) -> str:
    if code is None or pd.isna(code):
        return ""
    code = str(code).strip().upper()
    return POS_PT.get(code, code)


def pick_main_pos_from_list(lst):
    if not lst:
        return "NA"
    return str(lst[0]).strip().upper()


def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)

    # -------------------------
    # 1) Force numeric primeiro (pra derivados funcionarem certo)
    # -------------------------
    force_numeric = ["minutesplayed", "age", "rating", "goals", "assists", "appearances", "proposedmarketvalue", "playerid"]
    for c in force_numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # -------------------------
    # 2) Round só nas colunas numéricas (depois do to_numeric)
    # Obs: isso NÃO garante "7.70" visualmente; só arredonda valor.
    #      Para exibir 2 casas, é na formatação da tabela/gráfico.
    # -------------------------
    numeric_cols = df.select_dtypes(include="number").columns
    if len(numeric_cols) > 0:
        df.loc[:, numeric_cols] = df.loc[:, numeric_cols].round(2)

    # -------------------------
    # 3) Pré-cálculos (Series) -> vamos atribuir tudo via assign (anti-fragmentação)
    # -------------------------
    # positions_list
    if "positionsdetailed" in df.columns:
        positions_list = df["positionsdetailed"].apply(_safe_parse_list)
    else:
        positions_list = pd.Series([[] for _ in range(len(df))], index=df.index)

    # sofascore url/markdown (sem apply linha-a-linha)
    if "playerid" in df.columns and "playername" in df.columns:
        sofascore_url = [
            sofascore_player_url(n, pid)
            for n, pid in zip(df["playername"], df["playerid"])
        ]
        sofascore_url = pd.Series(sofascore_url, index=df.index)
        sofascore_md = sofascore_url.apply(lambda u: f"[Abrir]({u})" if u else "")
    else:
        sofascore_url = pd.Series(["" for _ in range(len(df))], index=df.index)
        sofascore_md = pd.Series(["" for _ in range(len(df))], index=df.index)

    # imagem: usa playerimageurl
    if "playerimageurl" in df.columns:
        photo_url = df["playerimageurl"].fillna("").astype(str)
    else:
        photo_url = pd.Series(["" for _ in range(len(df))], index=df.index)

    # Unique row id
    if "playerid" in df.columns:
        pid = pd.to_numeric(df["playerid"], errors="coerce")
        fallback = pd.Series(df.index.to_numpy() + 10**12, index=df.index)
        row_id = pid.fillna(fallback).astype("int64")
    else:
        row_id = (pd.Series(df.index.to_numpy() + 10**12, index=df.index)).astype("int64")

    # Derived metrics
    mins = df["minutesplayed"] if "minutesplayed" in df.columns else None
    goals = df["goals"] if "goals" in df.columns else None
    assists = df["assists"] if "assists" in df.columns else None

    if mins is not None and goals is not None:
        goals_per90 = goals / (mins / 90.0)
    else:
        goals_per90 = pd.Series([np.nan] * len(df), index=df.index)

    if mins is not None and assists is not None:
        assists_per90 = assists / (mins / 90.0)
    else:
        assists_per90 = pd.Series([np.nan] * len(df), index=df.index)

    if mins is not None and goals is not None and assists is not None:
        ga_per90 = (goals + assists) / (mins / 90.0)
    else:
        ga_per90 = pd.Series([np.nan] * len(df), index=df.index)

    if "rating" in df.columns and "proposedmarketvalue" in df.columns:
        value_performance = df["rating"] / df["proposedmarketvalue"].replace(0, np.nan)
    else:
        value_performance = pd.Series([np.nan] * len(df), index=df.index)

    # posições pt
    pos_code_main = positions_list.apply(pick_main_pos_from_list)
    pos_pt_main = pos_code_main.apply(pos_to_pt)

    # -------------------------
    # 4) Assign de uma vez (ANTI-FRAGMENTAÇÃO)
    # -------------------------
    df = df.assign(
        positions_list=positions_list,
        sofascore_url=sofascore_url,
        sofascore=sofascore_md,
        photo_url=photo_url,
        _row_id=row_id,
        goals_per90=goals_per90,
        assists_per90=assists_per90,
        ga_per90=ga_per90,
        value_performance=value_performance,
        pos_code_main=pos_code_main,
        pos_pt_main=pos_pt_main,
    )

    # -------------------------
    # 5) Defrag final (some com os warnings)
    # -------------------------
    df = df.copy()

    return df


DF = load_data()
