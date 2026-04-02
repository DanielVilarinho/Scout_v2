import re
import unicodedata
from urllib.parse import urlparse

import dash
from dash import dcc, html, Input, Output, State, ctx, ALL, no_update
import dash_bootstrap_components as dbc

from data import DF

dash.register_page(
    __name__,
    path="/team-builder",
    name="Team Builder",
    order=3,
    title="Team Builder",
)

df = DF.copy()

# =========================================================
# HELPERS DE COLUNAS
# =========================================================
def _find_col(candidates):
    cols = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    return None


COL_NAME = _find_col(["name", "playername", "player_name", "jogador", "nome"])
COL_TEAM = _find_col(["team", "teamname", "squad", "club", "currentteam", "clube"])
COL_POS = _find_col(["positionsdetailed", "positiondetailed", "positions", "position", "pos"])
COL_PID = _find_col(["playerid", "pid", "id", "player_id"])
COL_PHOTO = _find_col(["photo_url"])

if COL_NAME is None or COL_POS is None:
    raise ValueError("O DataFrame precisa ter nome e positionsdetailed.")

if COL_TEAM is None:
    df["_team_fallback"] = ""
    COL_TEAM = "_team_fallback"

if COL_PID is None:
    df["_pid_fallback"] = range(1, len(df) + 1)
    COL_PID = "_pid_fallback"

if COL_PHOTO is None:
    df["_photo_fallback"] = ""
    COL_PHOTO = "_photo_fallback"

df[COL_NAME] = df[COL_NAME].fillna("").astype(str)
df[COL_TEAM] = df[COL_TEAM].fillna("").astype(str)
df[COL_POS] = df[COL_POS].fillna("").astype(str)
df[COL_PID] = df[COL_PID].astype(str)
df[COL_PHOTO] = df[COL_PHOTO].fillna("").astype(str)

PLACEHOLDER_IMG = "https://placehold.co/120x120/png?text=Player"


# =========================================================
# NORMALIZAÇÃO
# =========================================================
def normalize_text(value):
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"[()\[\]{}|,/]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_url(url):
    url = str(url or "").strip()
    if not url or url.lower() == "nan":
        return PLACEHOLDER_IMG

    if url.startswith("//"):
        return "https:" + url

    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return url

    if "." in url and " " not in url and not url.startswith("/"):
        return "https://" + url

    return PLACEHOLDER_IMG


def build_player_label(row):
    name = row[COL_NAME]
    team = row[COL_TEAM]
    return f"{name} - {team}" if team else name


def build_photo_url(raw_url, player_id):
    raw_url = normalize_url(raw_url)

    if raw_url == PLACEHOLDER_IMG:
        return raw_url

    if "api.sofascore.app/api/v1/player/" in raw_url and "/image" in raw_url:
        if "?v=" not in raw_url:
            return f"{raw_url}?v={player_id}"

    return raw_url


def get_player_dict(row):
    player_id = str(row[COL_PID])
    return {
        "id": player_id,
        "name": row[COL_NAME],
        "team": row[COL_TEAM],
        "photo_url": build_photo_url(row[COL_PHOTO], player_id),
        "positionsdetailed": row[COL_POS],
        "label": build_player_label(row),
    }


# =========================================================
# MATCHING DE POSIÇÃO
# =========================================================
ROLE_ALIASES = {
    "GK": ["gk", "goalkeeper", "goal keeper", "goleiro"],

    "RB": ["rb", "right back", "lateral direito", "dr", "defender right"],
    "LB": ["lb", "left back", "lateral esquerdo", "dl", "defender left"],
    "RWB": ["rwb", "right wing back", "wing back right", "ala direito"],
    "LWB": ["lwb", "left wing back", "wing back left", "ala esquerdo"],

    "CB": ["cb", "centre back", "center back", "zagueiro", "dc", "defender centre", "defender center"],
    "LCB": ["cb", "centre back", "center back", "zagueiro", "dc", "left centre back", "left center back"],
    "RCB": ["cb", "centre back", "center back", "zagueiro", "dc", "right centre back", "right center back"],

    "DM": ["dm", "cdm", "defensive midfielder", "defensive midfield", "volante", "dmc", "midfielder defensive"],
    "CM": ["cm", "central midfielder", "central midfield", "meio campo", "meia central", "mc"],
    "LCM": ["cm", "central midfielder", "central midfield", "meio campo", "meia central", "mc"],
    "RCM": ["cm", "central midfielder", "central midfield", "meio campo", "meia central", "mc"],

    "LM": ["lm", "left midfielder", "left midfield", "meia esquerda", "ml"],
    "RM": ["rm", "right midfielder", "right midfield", "meia direita", "mr"],

    "CAM": ["cam", "am", "attacking midfielder", "attacking midfield", "meia ofensivo", "meia armador", "amc"],
    "LAM": ["lam", "left attacking midfield", "inside left", "left 10", "aml"],
    "RAM": ["ram", "right attacking midfield", "inside right", "right 10", "amr"],

    "LW": ["lw", "left wing", "wing left", "ponta esquerda", "left winger", "aml"],
    "RW": ["rw", "right wing", "wing right", "ponta direita", "right winger", "amr"],

    "ST": ["st", "cf", "striker", "forward", "atacante", "centroavante", "fw", "fc"],
    "LST": ["st", "cf", "striker", "forward", "atacante", "centroavante", "left striker"],
    "RST": ["st", "cf", "striker", "forward", "atacante", "centroavante", "right striker"],
}


def text_has_alias(text_norm, alias):
    alias = normalize_text(alias)
    if not alias:
        return False
    if " " in alias:
        return alias in text_norm
    return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text_norm) is not None


def position_matches_slot(position_text, slot):
    text_norm = normalize_text(position_text)
    if not text_norm:
        return False
    for alias in ROLE_ALIASES.get(slot, []):
        if text_has_alias(text_norm, alias):
            return True
    return False


# =========================================================
# CACHES
# =========================================================
df["_name_norm"] = df[COL_NAME].apply(normalize_text)
df["_team_norm"] = df[COL_TEAM].apply(normalize_text)
df["_pos_norm"] = df[COL_POS].apply(normalize_text)

POSITION_CACHE = None
PLAYER_LOOKUP = None


def get_position_cache():
    global POSITION_CACHE
    if POSITION_CACHE is None:
        cache = {}
        for slot in ROLE_ALIASES.keys():
            cache[slot] = df[df["_pos_norm"].apply(lambda x: position_matches_slot(x, slot))].copy()
        POSITION_CACHE = cache
    return POSITION_CACHE


def get_player_lookup():
    global PLAYER_LOOKUP
    if PLAYER_LOOKUP is None:
        PLAYER_LOOKUP = {
            str(row[COL_PID]): get_player_dict(row)
            for _, row in df.iterrows()
        }
    return PLAYER_LOOKUP


# =========================================================
# FORMAÇÕES
# =========================================================
FORMATIONS = {
    "4-4-2": [
        {"slot": "GK", "x": 50, "y": 8},
        {"slot": "LB", "x": 15, "y": 24},
        {"slot": "LCB", "x": 38, "y": 22},
        {"slot": "RCB", "x": 62, "y": 22},
        {"slot": "RB", "x": 85, "y": 24},
        {"slot": "LM", "x": 15, "y": 52},
        {"slot": "LCM", "x": 38, "y": 50},
        {"slot": "RCM", "x": 62, "y": 50},
        {"slot": "RM", "x": 85, "y": 52},
        {"slot": "LST", "x": 40, "y": 85},
        {"slot": "RST", "x": 60, "y": 85},
    ],
    "4-3-3": [
        {"slot": "GK", "x": 50, "y": 8},
        {"slot": "LB", "x": 15, "y": 24},
        {"slot": "LCB", "x": 38, "y": 22},
        {"slot": "RCB", "x": 62, "y": 22},
        {"slot": "RB", "x": 85, "y": 24},
        {"slot": "LCM", "x": 32, "y": 52},
        {"slot": "DM", "x": 50, "y": 48},
        {"slot": "RCM", "x": 68, "y": 52},
        {"slot": "LW", "x": 18, "y": 82},
        {"slot": "ST", "x": 50, "y": 88},
        {"slot": "RW", "x": 82, "y": 82},
    ],
    "4-2-3-1": [
        {"slot": "GK", "x": 50, "y": 8},
        {"slot": "LB", "x": 15, "y": 24},
        {"slot": "LCB", "x": 38, "y": 22},
        {"slot": "RCB", "x": 62, "y": 22},
        {"slot": "RB", "x": 85, "y": 24},
        {"slot": "LCM", "x": 40, "y": 50},
        {"slot": "RCM", "x": 60, "y": 50},
        {"slot": "LW", "x": 20, "y": 70},
        {"slot": "CAM", "x": 50, "y": 68},
        {"slot": "RW", "x": 80, "y": 70},
        {"slot": "ST", "x": 50, "y": 88},
    ],
    "3-5-2": [
        {"slot": "GK", "x": 50, "y": 8},
        {"slot": "LCB", "x": 28, "y": 22},
        {"slot": "CB", "x": 50, "y": 20},
        {"slot": "RCB", "x": 72, "y": 22},
        {"slot": "LM", "x": 10, "y": 52},
        {"slot": "LCM", "x": 35, "y": 54},
        {"slot": "CAM", "x": 50, "y": 66},
        {"slot": "RCM", "x": 65, "y": 54},
        {"slot": "RM", "x": 90, "y": 52},
        {"slot": "LST", "x": 40, "y": 86},
        {"slot": "RST", "x": 60, "y": 86},
    ],
    "3-4-3": [
        {"slot": "GK", "x": 50, "y": 8},
        {"slot": "LCB", "x": 28, "y": 22},
        {"slot": "CB", "x": 50, "y": 20},
        {"slot": "RCB", "x": 72, "y": 22},
        {"slot": "LM", "x": 13, "y": 52},
        {"slot": "LCM", "x": 40, "y": 54},
        {"slot": "RCM", "x": 60, "y": 54},
        {"slot": "RM", "x": 87, "y": 52},
        {"slot": "LW", "x": 18, "y": 84},
        {"slot": "ST", "x": 50, "y": 88},
        {"slot": "RW", "x": 82, "y": 84},
    ],
    "5-3-2": [
        {"slot": "GK", "x": 50, "y": 8},
        {"slot": "LWB", "x": 10, "y": 28},
        {"slot": "LCB", "x": 28, "y": 22},
        {"slot": "CB", "x": 50, "y": 20},
        {"slot": "RCB", "x": 72, "y": 22},
        {"slot": "RWB", "x": 90, "y": 28},
        {"slot": "LCM", "x": 35, "y": 54},
        {"slot": "CM", "x": 50, "y": 50},
        {"slot": "RCM", "x": 65, "y": 54},
        {"slot": "LST", "x": 40, "y": 86},
        {"slot": "RST", "x": 60, "y": 86},
    ],
    "4-1-4-1": [
        {"slot": "GK", "x": 50, "y": 8},
        {"slot": "LB", "x": 15, "y": 24},
        {"slot": "LCB", "x": 38, "y": 22},
        {"slot": "RCB", "x": 62, "y": 22},
        {"slot": "RB", "x": 85, "y": 24},
        {"slot": "DM", "x": 50, "y": 46},
        {"slot": "LM", "x": 15, "y": 60},
        {"slot": "LCM", "x": 38, "y": 58},
        {"slot": "RCM", "x": 62, "y": 58},
        {"slot": "RM", "x": 85, "y": 60},
        {"slot": "ST", "x": 50, "y": 88},
    ],
}

BENCH_SLOTS = [f"BENCH_{i}" for i in range(1, 13)]


# =========================================================
# COMPONENTES VISUAIS
# =========================================================
def pitch_background():
    return html.Div(
        style={
            "position": "absolute",
            "inset": "0",
            "borderRadius": "18px",
            "overflow": "hidden",
            "background": """
                linear-gradient(
                    90deg,
                    rgba(255,255,255,0.05) 0%,
                    rgba(255,255,255,0.05) 10%,
                    rgba(255,255,255,0.00) 10%,
                    rgba(255,255,255,0.00) 20%,
                    rgba(255,255,255,0.05) 20%,
                    rgba(255,255,255,0.05) 30%,
                    rgba(255,255,255,0.00) 30%,
                    rgba(255,255,255,0.00) 40%,
                    rgba(255,255,255,0.05) 40%,
                    rgba(255,255,255,0.05) 50%,
                    rgba(255,255,255,0.00) 50%,
                    rgba(255,255,255,0.00) 60%,
                    rgba(255,255,255,0.05) 60%,
                    rgba(255,255,255,0.05) 70%,
                    rgba(255,255,255,0.00) 70%,
                    rgba(255,255,255,0.00) 80%,
                    rgba(255,255,255,0.05) 80%,
                    rgba(255,255,255,0.05) 90%,
                    rgba(255,255,255,0.00) 90%,
                    rgba(255,255,255,0.00) 100%
                ),
                linear-gradient(180deg, #82d983 0%, #69c96f 100%)
            """,
        },
        children=[
            html.Div(style={"position": "absolute", "left": "2%", "top": "2%", "width": "96%", "height": "96%", "border": "2px solid rgba(255,255,255,0.95)", "borderRadius": "10px"}),
            html.Div(style={"position": "absolute", "left": "2%", "top": "50%", "width": "96%", "height": "0", "borderTop": "2px solid rgba(255,255,255,0.95)", "transform": "translateY(-1px)"}),
            html.Div(style={"position": "absolute", "left": "50%", "top": "50%", "width": "20%", "height": "20%", "border": "2px solid rgba(255,255,255,0.95)", "borderRadius": "50%", "transform": "translate(-50%, -50%)"}),
            html.Div(style={"position": "absolute", "left": "50%", "top": "50%", "width": "8px", "height": "8px", "background": "rgba(255,255,255,0.95)", "borderRadius": "50%", "transform": "translate(-50%, -50%)"}),
            html.Div(style={"position": "absolute", "left": "21%", "top": "2%", "width": "58%", "height": "14%", "border": "2px solid rgba(255,255,255,0.95)"}),
            html.Div(style={"position": "absolute", "left": "36%", "top": "2%", "width": "28%", "height": "5%", "border": "2px solid rgba(255,255,255,0.95)"}),
            html.Div(style={"position": "absolute", "left": "21%", "bottom": "2%", "width": "58%", "height": "14%", "border": "2px solid rgba(255,255,255,0.95)"}),
            html.Div(style={"position": "absolute", "left": "36%", "bottom": "2%", "width": "28%", "height": "5%", "border": "2px solid rgba(255,255,255,0.95)"}),
        ],
    )


def build_slot_button(slot_key, display_text, player, x, y, size=78):
    button_style = {
        "position": "absolute",
        "left": f"{x}%",
        "top": f"{y}%",
        "transform": "translate(-50%, -50%)",
        "width": f"{size}px",
        "height": f"{size}px",
        "borderRadius": "50%",
        "border": "2px solid rgba(255,255,255,0.95)",
        "background": "rgba(255,255,255,0.18)",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "overflow": "hidden",
        "cursor": "pointer",
        "boxShadow": "0 4px 14px rgba(0,0,0,0.22)",
        "zIndex": 20,
        "padding": "0",
    }

    if player:
        content = html.Img(
            src=player.get("photo_url") or PLACEHOLDER_IMG,
            crossOrigin="anonymous",
            referrerPolicy="no-referrer",
            style={"width": "100%", "height": "100%", "objectFit": "cover", "display": "block"},
        )
    else:
        content = html.Span(
            display_text,
            style={
                "color": "white",
                "fontWeight": "700",
                "fontSize": "12px",
                "textAlign": "center",
                "lineHeight": "1",
            },
        )

    return html.Button(
        content,
        id={"type": "tb-slot-btn", "slot": slot_key},
        n_clicks=0,
        type="button",
        style=button_style,
        title=slot_key,
    )


def build_field_slot_component(slot_def, selected_players):
    slot = slot_def["slot"]
    x = slot_def["x"]
    y = 100 - slot_def["y"]

    player = (selected_players or {}).get(slot)
    btn = build_slot_button(slot, slot, player, x, y, size=78)

    if not player:
        return [btn]

    label = html.Div(
        [
            html.Div(
                player["name"],
                style={
                    "fontWeight": "700",
                    "fontSize": "12px",
                    "lineHeight": "1.1",
                    "whiteSpace": "nowrap",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                    "maxWidth": "130px",
                },
            ),
            html.Div(
                player["team"],
                style={
                    "fontSize": "11px",
                    "opacity": 0.9,
                    "whiteSpace": "nowrap",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                    "maxWidth": "130px",
                },
            ),
        ],
        style={
            "position": "absolute",
            "left": f"{x}%",
            "top": f"{y - 10}%",
            "transform": "translateX(-50%)",
            "background": "rgba(0,0,0,0.28)",
            "color": "white",
            "padding": "4px 8px",
            "borderRadius": "10px",
            "border": "1px solid rgba(255,255,255,0.20)",
            "textAlign": "center",
            "zIndex": 15,
            "backdropFilter": "blur(4px)",
        },
    )

    return [btn, label]


def build_pitch_slots(formation_name, selected_players):
    children = []
    for slot_def in FORMATIONS[formation_name]:
        children.extend(build_field_slot_component(slot_def, selected_players))
    return children


def build_bench_area(selected_players):
    bench_items = []
    xs = [6, 14, 22, 30, 38, 46, 54, 62, 70, 78, 86, 94]

    for idx, slot in enumerate(BENCH_SLOTS):
        player = (selected_players or {}).get(slot)
        x = xs[idx]
        btn = build_slot_button(slot, f"R{idx+1}", player, x, 58, size=68)

        card = [btn]
        if player:
            card.append(
                html.Div(
                    [
                        html.Div(
                            player["name"],
                            style={
                                "fontWeight": "700",
                                "fontSize": "11px",
                                "lineHeight": "1.1",
                                "whiteSpace": "nowrap",
                                "overflow": "hidden",
                                "textOverflow": "ellipsis",
                                "maxWidth": "90px",
                            },
                        ),
                        html.Div(
                            player["team"],
                            style={
                                "fontSize": "10px",
                                "opacity": 0.9,
                                "whiteSpace": "nowrap",
                                "overflow": "hidden",
                                "textOverflow": "ellipsis",
                                "maxWidth": "90px",
                            },
                        ),
                    ],
                    style={
                        "position": "absolute",
                        "left": f"{x}%",
                        "top": "82%",
                        "transform": "translateX(-50%)",
                        "background": "rgba(0,0,0,0.24)",
                        "color": "white",
                        "padding": "3px 6px",
                        "borderRadius": "8px",
                        "border": "1px solid rgba(255,255,255,0.18)",
                        "textAlign": "center",
                        "zIndex": 15,
                    },
                )
            )
        bench_items.extend(card)

    return html.Div(
        style={
            "position": "relative",
            "width": "100%",
            "height": "180px",
            "marginTop": "18px",
            "borderRadius": "18px",
            "overflow": "hidden",
            "background": "linear-gradient(180deg, #6fbf73 0%, #5dad63 100%)",
            "border": "2px solid rgba(255,255,255,0.28)",
            "boxShadow": "0 8px 24px rgba(0,0,0,0.12)",
        },
        children=[
            html.Div(
                "Reservas",
                style={
                    "position": "absolute",
                    "left": "50%",
                    "top": "14%",
                    "transform": "translateX(-50%)",
                    "color": "white",
                    "fontWeight": "700",
                    "fontSize": "22px",
                    "letterSpacing": "0.5px",
                    "textShadow": "0 2px 6px rgba(0,0,0,0.20)",
                },
            ),
            html.Div(
                style={
                    "position": "absolute",
                    "left": "2%",
                    "top": "26%",
                    "width": "96%",
                    "height": "56%",
                    "border": "2px dashed rgba(255,255,255,0.30)",
                    "borderRadius": "16px",
                }
            ),
            *bench_items,
        ],
    )


# =========================================================
# LAYOUT
# =========================================================
layout = dbc.Container(
    fluid=True,
    className="py-3",
    children=[
        html.Script(src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"),

        dcc.Store(id="tb-selected-players", data={}),
        dcc.Store(id="tb-active-slot", data=None),
        dcc.Store(id="tb-player-search-reset", data=0),
        dcc.Store(id="tb-slot-open-seq", data=0),

        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("Team Builder", className="mb-1"),
                        html.Div(
                            "Escolha a formação, monte o time titular e o banco, e tire um screenshot da montagem.",
                            className="text-secondary mb-3",
                        ),
                    ],
                    md=8,
                ),
                dbc.Col(
                    [
                        dbc.Label("Formação", className="fw-semibold"),
                        dcc.Dropdown(
                            id="tb-formation",
                            options=[{"label": k, "value": k} for k in FORMATIONS.keys()],
                            value="4-3-3",
                            clearable=False,
                        ),
                    ],
                    md=4,
                ),
            ],
            className="mb-3",
        ),

        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    "Tirar screenshot",
                                                    id="tb-screenshot-btn",
                                                    color="primary",
                                                    className="mb-3",
                                                ),
                                                width="auto",
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        id="tb-capture-area",
                                        children=[
                                            html.Div(
                                                id="tb-pitch-container",
                                                style={
                                                    "position": "relative",
                                                    "width": "100%",
                                                    "height": "820px",
                                                    "borderRadius": "18px",
                                                    "overflow": "hidden",
                                                    "background": "#69b96f",
                                                },
                                            ),
                                            html.Div(id="tb-bench-container"),
                                        ],
                                    ),
                                ]
                            ),
                            className="shadow-sm border-0",
                        )
                    ],
                    lg=9,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                dbc.Button(
                                    "Limpar escalação",
                                    id="tb-clear-all",
                                    color="danger",
                                    outline=True,
                                    className="w-100",
                                )
                            ),
                            className="shadow-sm border-0 mb-3",
                        ),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Titulares e Reservas", className="mb-3"),
                                    html.Div(id="tb-selected-list"),
                                ]
                            ),
                            className="shadow-sm border-0",
                        ),
                    ],
                    lg=3,
                ),
            ]
        ),

        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle(id="tb-modal-title")),
                dbc.ModalBody(
                    dcc.Dropdown(
                        id="tb-player-dropdown",
                        options=[],
                        value=None,
                        placeholder="Pesquise e selecione um jogador",
                        searchable=True,
                        clearable=True,
                        persistence=False,
                    )
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button("Remover jogador do slot", id="tb-remove-player", color="warning", outline=True),
                        dbc.Button("Cancelar", id="tb-close-modal", color="secondary", outline=True),
                        dbc.Button("Confirmar", id="tb-confirm-player", color="primary"),
                    ]
                ),
            ],
            id="tb-player-modal",
            is_open=False,
            size="lg",
            centered=True,
        ),

        html.Div(id="tb-screenshot-status", style={"display": "none"}),
        html.Div(id="tb-focus-status", style={"display": "none"}),
    ],
)


# =========================================================
# CALLBACKS
# =========================================================
@dash.callback(
    Output("tb-pitch-container", "children"),
    Output("tb-bench-container", "children"),
    Input("tb-formation", "value"),
    Input("tb-selected-players", "data"),
)
def render_pitch_and_bench(formation_name, selected_players):
    selected_players = selected_players or {}
    field_children = [pitch_background()] + build_pitch_slots(formation_name, selected_players)
    bench_children = build_bench_area(selected_players)
    return field_children, bench_children


@dash.callback(
    Output("tb-active-slot", "data"),
    Output("tb-player-modal", "is_open"),
    Output("tb-slot-open-seq", "data"),
    Output("tb-player-search-reset", "data"),
    Output("tb-player-dropdown", "value", allow_duplicate=True),
    Input({"type": "tb-slot-btn", "slot": ALL}, "n_clicks"),
    Input("tb-close-modal", "n_clicks"),
    Input("tb-confirm-player", "n_clicks"),
    Input("tb-remove-player", "n_clicks"),
    State({"type": "tb-slot-btn", "slot": ALL}, "id"),
    State("tb-slot-open-seq", "data"),
    State("tb-player-search-reset", "data"),
    State("tb-active-slot", "data"),
    prevent_initial_call=True,
)
def open_close_modal(slot_clicks, n_close, n_confirm, n_remove, slot_ids, open_seq, search_reset, active_slot):
    trigger = ctx.triggered_id

    if isinstance(trigger, dict) and trigger.get("type") == "tb-slot-btn":
        triggered_slot = trigger.get("slot")

        clicked_value = 0
        for btn_id, clicks in zip(slot_ids or [], slot_clicks or []):
            if btn_id.get("slot") == triggered_slot:
                clicked_value = clicks or 0
                break

        if clicked_value <= 0:
            return no_update, no_update, no_update, no_update, no_update

        return triggered_slot, True, (open_seq or 0) + 1, (search_reset or 0) + 1, None

    if trigger in ["tb-close-modal", "tb-confirm-player", "tb-remove-player"]:
        return active_slot, False, open_seq, search_reset, None

    return no_update, no_update, no_update, no_update, no_update


@dash.callback(
    Output("tb-player-dropdown", "search_value"),
    Input("tb-player-search-reset", "data"),
    prevent_initial_call=True,
)
def reset_dropdown_search(_):
    return ""


@dash.callback(
    Output("tb-modal-title", "children"),
    Output("tb-player-dropdown", "options"),
    Output("tb-player-dropdown", "value"),
    Input("tb-active-slot", "data"),
    Input("tb-slot-open-seq", "data"),
    Input("tb-player-dropdown", "search_value"),
    State("tb-selected-players", "data"),
    State("tb-player-dropdown", "value"),
)
def update_player_options(active_slot, open_seq, search_value, selected_players, current_dropdown_value):
    if not active_slot:
        return "Selecionar jogador", [], None

    selected_players = selected_players or {}
    is_bench = str(active_slot).startswith("BENCH_")

    if is_bench:
        base_df = df.copy()
        modal_title = f"Selecionar jogador para {active_slot.replace('BENCH_', 'Reserva ')}"
    else:
        position_cache = get_position_cache()
        base_df = position_cache.get(active_slot, df.iloc[0:0]).copy()
        modal_title = f"Selecionar jogador para {active_slot}"

    current_slot_player = selected_players.get(active_slot)

    if ctx.triggered_id in ["tb-active-slot", "tb-slot-open-seq"]:
        selected_value = str(current_slot_player.get("id")) if current_slot_player else None
    else:
        selected_value = str(current_dropdown_value) if current_dropdown_value else None

    if search_value and search_value.strip():
        terms = normalize_text(search_value).split()
        filtered = base_df
        for term in terms:
            filtered = filtered[
                filtered["_name_norm"].str.contains(term, na=False)
                | filtered["_team_norm"].str.contains(term, na=False)
            ]
        filtered = filtered.sort_values([COL_NAME, COL_TEAM]).head(120)
    else:
        filtered = base_df.sort_values([COL_NAME, COL_TEAM]).head(80)

    options = []
    for _, row in filtered.iterrows():
        player = get_player_dict(row)
        options.append({"label": player["label"], "value": player["id"]})

    if selected_value:
        exists = any(str(opt["value"]) == str(selected_value) for opt in options)
        if not exists:
            row = base_df[base_df[COL_PID].astype(str) == str(selected_value)]
            if row.empty:
                row = df[df[COL_PID].astype(str) == str(selected_value)]
            if not row.empty:
                player = get_player_dict(row.iloc[0])
                options = [{"label": player["label"], "value": player["id"]}] + options

    return modal_title, options, selected_value


@dash.callback(
    Output("tb-selected-players", "data"),
    Input("tb-confirm-player", "n_clicks"),
    Input("tb-remove-player", "n_clicks"),
    Input("tb-clear-all", "n_clicks"),
    State("tb-active-slot", "data"),
    State("tb-player-dropdown", "value"),
    State("tb-selected-players", "data"),
    prevent_initial_call=True,
)
def select_or_remove_player(n_confirm, n_remove, n_clear, active_slot, selected_player_id, selected_players):
    trigger = ctx.triggered_id
    selected_players = dict(selected_players or {})

    if trigger == "tb-clear-all":
        return {}

    if not active_slot:
        return no_update

    if trigger == "tb-remove-player":
        selected_players.pop(active_slot, None)
        return selected_players

    if trigger == "tb-confirm-player":
        if not selected_player_id:
            return selected_players

        player_lookup = get_player_lookup()
        player = player_lookup.get(str(selected_player_id))
        if not player:
            return selected_players

        selected_players[active_slot] = player
        return selected_players

    return no_update


@dash.callback(
    Output("tb-selected-list", "children"),
    Input("tb-selected-players", "data"),
    Input("tb-formation", "value"),
)
def render_selected_list(selected_players, formation_name):
    selected_players = selected_players or {}
    starters = [x["slot"] for x in FORMATIONS[formation_name]]

    blocks = [html.H6("Titulares", className="mb-2")]

    for slot in starters:
        p = selected_players.get(slot)
        if not p:
            blocks.append(
                dbc.Card(
                    dbc.CardBody([html.Div(slot, className="fw-bold"), html.Div("Vazio", className="text-secondary small")]),
                    className="mb-2 border-0 bg-dark-subtle",
                )
            )
        else:
            blocks.append(
                dbc.Card(
                    dbc.CardBody(
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Img(
                                        src=p.get("photo_url") or PLACEHOLDER_IMG,
                                        crossOrigin="anonymous",
                                        referrerPolicy="no-referrer",
                                        style={
                                            "width": "42px",
                                            "height": "42px",
                                            "borderRadius": "50%",
                                            "objectFit": "cover",
                                            "display": "block",
                                        },
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    [
                                        html.Div(slot, className="fw-bold"),
                                        html.Div(p["name"], className="small"),
                                        html.Div(p["team"], className="text-secondary small"),
                                    ]
                                ),
                            ],
                            className="g-2 align-items-center",
                        )
                    ),
                    className="mb-2 border-0 bg-dark-subtle",
                )
            )

    blocks.append(html.Hr())
    blocks.append(html.H6("Reservas", className="mb-2"))

    for idx, slot in enumerate(BENCH_SLOTS, start=1):
        p = selected_players.get(slot)
        label = f"R{idx}"

        if not p:
            blocks.append(
                dbc.Card(
                    dbc.CardBody([html.Div(label, className="fw-bold"), html.Div("Vazio", className="text-secondary small")]),
                    className="mb-2 border-0 bg-dark-subtle",
                )
            )
        else:
            blocks.append(
                dbc.Card(
                    dbc.CardBody(
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Img(
                                        src=p.get("photo_url") or PLACEHOLDER_IMG,
                                        crossOrigin="anonymous",
                                        referrerPolicy="no-referrer",
                                        style={
                                            "width": "42px",
                                            "height": "42px",
                                            "borderRadius": "50%",
                                            "objectFit": "cover",
                                            "display": "block",
                                        },
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    [
                                        html.Div(label, className="fw-bold"),
                                        html.Div(p["name"], className="small"),
                                        html.Div(p["team"], className="text-secondary small"),
                                    ]
                                ),
                            ],
                            className="g-2 align-items-center",
                        )
                    ),
                    className="mb-2 border-0 bg-dark-subtle",
                )
            )

    return blocks


# =========================================================
# CLIENTSIDE CALLBACKS
# =========================================================
app = dash.get_app()

app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) {
            return window.dash_clientside.no_update;
        }

        const target = document.getElementById("tb-capture-area");
        if (!target || typeof html2canvas === "undefined") {
            return "erro";
        }

        html2canvas(target, {
            useCORS: true,
            allowTaint: false,
            backgroundColor: null,
            scale: 2
        }).then(function(canvas) {
            const link = document.createElement("a");
            link.download = "team_builder.png";
            link.href = canvas.toDataURL("image/png");
            link.click();
        });

        return "ok-" + n_clicks;
    }
    """,
    Output("tb-screenshot-status", "children"),
    Input("tb-screenshot-btn", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(is_open) {
        if (!is_open) {
            return window.dash_clientside.no_update;
        }

        setTimeout(function() {
            const modal = document.getElementById("tb-player-modal");
            if (!modal) return;

            const input = modal.querySelector("input");
            if (!input) return;

            input.focus();
            input.click();
        }, 150);

        return "focused";
    }
    """,
    Output("tb-focus-status", "children"),
    Input("tb-player-modal", "is_open"),
    prevent_initial_call=True,
)