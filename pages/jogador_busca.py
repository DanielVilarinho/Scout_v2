# pages/jogador_busca.py
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

from data import DF  # precisa ter playerid + playername (+ teamname)

dash.register_page(__name__, path="/jogadores", name="Jogadores", order=2, title="Buscar jogador")

df = DF.copy()

def make_player_options(dff: pd.DataFrame):
    if dff is None or dff.empty:
        return []
    if not {"playerid", "playername"}.issubset(dff.columns):
        return []

    # teamname é opcional, mas no seu DF existe
    has_team = "teamname" in dff.columns

    cols = ["playerid", "playername"] + (["teamname"] if has_team else [])
    tmp = dff[cols].copy()

    tmp = tmp.dropna(subset=["playerid", "playername"])
    tmp["playerid"] = pd.to_numeric(tmp["playerid"], errors="coerce")
    tmp = tmp.dropna(subset=["playerid"])
    tmp["playerid"] = tmp["playerid"].astype("int64")

    if has_team:
        tmp["teamname"] = tmp["teamname"].fillna("").astype(str).str.strip()
    tmp["playername"] = tmp["playername"].astype(str).str.strip()

    tmp = tmp.drop_duplicates(subset=["playerid"])
    tmp = tmp.sort_values("playername")

    options = []
    if has_team:
        for _, r in tmp.iterrows():
            name = r["playername"]
            team = r["teamname"]
            label = f"{name} - {team}" if team else name
            options.append({"label": label, "value": int(r["playerid"])})
    else:
        options = [{"label": r["playername"], "value": int(r["playerid"])} for _, r in tmp.iterrows()]

    return options


layout = dbc.Container(
    fluid=True,
    style={"maxWidth": "1100px"},
    children=[
        dcc.Location(id="player_search_nav", refresh=True),

        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.H2("Buscar jogador", className="mb-1"),
                        html.Div("Pesquise pelo nome e abra a página individual.", className="text-muted"),
                    ],
                    className="py-3"
                )
            )
        ),

        dbc.Card(
            dbc.CardBody(
                [
                    html.Label("Jogador", className="fw-semibold"),
                    dcc.Dropdown(
                        id="player_search_dd",
                        options=make_player_options(df),
                        value=None,
                        placeholder="Digite para pesquisar…",
                        searchable=True,
                        clearable=True,
                    ),

                    html.Div(className="mt-3"),
                    dbc.Button("Ir para a página do jogador", id="go_player_btn", color="primary", disabled=True),
                    html.Hr(),
                    dbc.Alert("Dica: você também pode abrir direto via URL: /jogador/<playerid>.", color="info"),
                ]
            )
        ),
    ]
)


@dash.callback(
    Output("go_player_btn", "disabled"),
    Input("player_search_dd", "value"),
)
def toggle_btn(pid):
    return pid is None


@dash.callback(
    Output("player_search_nav", "pathname"),
    Input("go_player_btn", "n_clicks"),
    State("player_search_dd", "value"),
    prevent_initial_call=True
)
def go_to_player(n, pid):
    if not n or pid is None:
        return dash.no_update
    return f"/jogador/{int(pid)}"
