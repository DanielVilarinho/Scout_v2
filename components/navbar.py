import dash
import dash_bootstrap_components as dbc


def _order_value(p: dict) -> int:
    """
    Garante que o 'order' seja sempre um inteiro.
    Se vier None, vazio, string inválida, etc, joga para o final.
    """
    v = p.get("order", 0)

    if v is None:
        return 10**9

    # já é número
    if isinstance(v, (int, float)):
        try:
            return int(v)
        except Exception:
            return 10**9

    # tenta converter string
    try:
        s = str(v).strip()
        if s == "":
            return 10**9
        return int(float(s))
    except Exception:
        return 10**9


def make_navbar():
    pages = [
    p for p in dash.page_registry.values()
    if not p.get("hidden", False)
    ]

    # ordena sem quebrar com None
    pages = sorted(pages, key=lambda p: (_order_value(p), str(p.get("name", "")).lower()))

    items = []
    for p in pages:
        name = p.get("name", "Página")
        path = p.get("path", "/")
        items.append(
            dbc.NavItem(
                dbc.NavLink(name, href=path, active="exact")
            )
        )

    return dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand("Scout v2", href="/"),
                dbc.Nav(items, className="ms-auto", navbar=True),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        sticky="top",
    )
