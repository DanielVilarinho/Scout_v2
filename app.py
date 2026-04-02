from dash import Dash, html
import dash_bootstrap_components as dbc
import dash

from flask import Response, request
import requests

from components.navbar import make_navbar

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.FLATLY],
)
server = app.server
app.title = "Player Stats Dashboard"

GLOBAL_CSS = """
html, body { height: 100%; }
body {
  margin: 0;
  background: linear-gradient(135deg, #d9f1ff 0%, #eaf7ff 35%, #d6ecff 70%, #cfe8ff 100%);
  background-attachment: fixed;
}
.card {
  border-radius: 14px !important;
  box-shadow: 0 10px 25px rgba(0,0,0,0.07) !important;
  border: 1px solid rgba(0,0,0,0.05) !important;
}
.small-help { font-size: 0.85rem; }
"""


app.layout = dbc.Container(
    fluid=True,
    children=[

        dash.page_container,
    ],
    style={"maxWidth": "1600px"},
)

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)