# ============================================================
# ECAP STORE — Dash app (version définitive corrigée, bon ordre)
# ============================================================

import pandas as pd
import numpy as np
import calendar

import dash
from dash import html, dcc, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px


# ============================================================
# 1) DATA (adapter le chemin si besoin)
# ============================================================

raw_df = pd.read_csv("datasets/data.csv")

# Colonnes attendues
cols = [
    "CustomerID", "Gender", "Location", "Product_Category",
    "Quantity", "Avg_Price", "Transaction_Date", "Month", "Discount_pct"
]

df_base = raw_df[cols].copy()

# Nettoyage / types
df_base["CustomerID"] = pd.to_numeric(df_base["CustomerID"], errors="coerce").fillna(0).astype(int)
df_base["Transaction_Date"] = pd.to_datetime(df_base["Transaction_Date"], errors="coerce")
df_base = df_base.dropna(subset=["Transaction_Date"]).copy()

df_base["Quantity"] = pd.to_numeric(df_base["Quantity"], errors="coerce").fillna(0)
df_base["Avg_Price"] = pd.to_numeric(df_base["Avg_Price"], errors="coerce").fillna(0)
df_base["Discount_pct"] = pd.to_numeric(df_base["Discount_pct"], errors="coerce").fillna(0)
df_base["Month"] = pd.to_numeric(df_base["Month"], errors="coerce").fillna(0).astype(int)

# Discount : 30 -> 0.30
df_base["_disc"] = np.where(
    df_base["Discount_pct"] > 1,
    df_base["Discount_pct"] / 100.0,
    df_base["Discount_pct"]
)

# Total_price = CA ligne
df_base["Total_price"] = df_base["Quantity"] * df_base["Avg_Price"] * (1 - df_base["_disc"])

# Sécurité
df_base["Gender"] = df_base["Gender"].fillna("NA").astype(str)
df_base["Location"] = df_base["Location"].fillna("NA").astype(str)
df_base["Product_Category"] = df_base["Product_Category"].fillna("NA").astype(str)


# ============================================================
# 2) FONCTIONS METIER
# ============================================================

def indicateur_du_mois(data: pd.DataFrame, current_month: int = 12, freq: bool = True, abbr: bool = False):
    """
    KPI du mois courant vs mois précédent.
    freq=True  -> nb ventes (nb de lignes)
    freq=False -> chiffre d'affaires (somme Total_price)
    Retour: (label_mois, valeur_mois, delta)
    """
    cur = data[data["Month"] == current_month]
    prev = data[data["Month"] == (current_month - 1)]

    if freq:
        v_cur = len(cur)
        v_prev = len(prev)
    else:
        v_cur = cur["Total_price"].sum()
        v_prev = prev["Total_price"].sum()

    delta = v_cur - v_prev

    if 1 <= current_month <= 12:
        m_label = calendar.month_abbr[current_month] if abbr else calendar.month_name[current_month]
    else:
        m_label = "Mois"

    return m_label, v_cur, delta


def frequence_meilleure_vente(data: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    """
    Top produits selon fréquence de vente (nombre de lignes),
    puis agrégation par Gender.
    Retour: Product_Category, Gender, Frequence
    """
    top_prod = (
        data.groupby("Product_Category")
        .size()
        .sort_values(ascending=False)
        .head(top)
        .index
    )

    out = data[data["Product_Category"].isin(top_prod)].copy()

    out = (
        out.groupby(["Product_Category", "Gender"])
        .size()
        .reset_index(name="Frequence")
    )

    return out

# ============================================================
# 3) HELPERS AFFICHAGE
# ============================================================

def fmt_k(x):
    x = float(x)
    return f"{x/1000:.0f}k" if abs(x) >= 1000 else f"{int(round(x)):,}".replace(",", " ")

def kpi_block(month_label, value, delta, is_money=True):
    if is_money:
        delta_txt = fmt_k(abs(delta))
        value_txt = fmt_k(value)
        sign = "−" if delta < 0 else "+"
        color = "red" if delta < 0 else "green"
        arrow = "▼ " if delta < 0 else "▲ "
        delta_show = f"{arrow}{sign}{delta_txt}"
    else:
        value_txt = f"{int(value):,}".replace(",", " ")
        color = "green" if delta >= 0 else "red"
        arrow = "▲ " if delta >= 0 else "▼ "
        delta_show = f"{arrow}{abs(int(delta)):,}".replace(",", " ")

    return html.Div([
        html.Div(month_label, style={"color": "#666"}),
        html.Div(value_txt, style={"fontSize": "56px", "fontWeight": "700", "lineHeight": "1"}),
        html.Div(delta_show, style={"fontSize": "28px", "fontWeight": "500", "color": color}),
    ], style={"border": "1px solid #ddd", "padding": "12px", "backgroundColor": "white"})


# ============================================================
# 4) DASH APP
# ============================================================

zone_col = "Location"
zones = sorted(df_base[zone_col].dropna().astype(str).unique().tolist())

HEADER_STYLE = {"backgroundColor": "#b9dbe7", "padding": "10px 12px", "border": "2px solid #333"}
PANEL_STYLE  = {"border": "1px solid #ddd", "padding": "10px", "backgroundColor": "white"}

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server= app.server

app.layout = dbc.Container([

    dbc.Row([
        dbc.Col(html.H4("ECAP Store", style={"margin": 0}), md=6),
        dbc.Col(
            dcc.Dropdown(
                id="zone_dd",
                options=[{"label": z, "value": z} for z in zones],
                value=[],
                multi=True,
                placeholder="Choisissez une ou plusieurs zones",
                style={"width": "360px"},
            ),
            md=6,
            style={"display": "flex", "justifyContent": "flex-end"},
        )
    ], style=HEADER_STYLE, className="g-0"),

    dbc.Row([

        dbc.Col([
            dbc.Row([
                dbc.Col(html.Div(id="kpi_ca"), md=6),
                dbc.Col(html.Div(id="kpi_n"), md=6),
            ], className="g-3 mt-2"),

            html.Div(
                [dcc.Graph(id="bar_top10", config={"displayModeBar": False})],
                style=PANEL_STYLE,
                className="mt-3"
            ),

        ], md=4),

        dbc.Col([
            html.Div(
                [dcc.Graph(id="line_week", config={"displayModeBar": False})],
                style=PANEL_STYLE,
                className="mt-2"
            ),

            html.Div([
                html.Div("Table des 100 dernières ventes", style={"fontWeight": "600", "marginBottom": "6px"}),
                dash_table.DataTable(
                    id="tbl_last100",
                    page_size=10,
                    style_table={"overflowX": "auto"},
                    style_cell={"fontSize": "12px", "padding": "4px", "textAlign": "left"},
                    style_header={"fontWeight": "600", "backgroundColor": "#f5f5f5"},
                )
            ], style=PANEL_STYLE, className="mt-3"),

        ], md=8),

    ], className="g-3")

], fluid=True)


# ============================================================
# 5) CALLBACK
# ============================================================

@app.callback(
    Output("kpi_ca", "children"),
    Output("kpi_n", "children"),
    Output("bar_top10", "figure"),
    Output("line_week", "figure"),
    Output("tbl_last100", "columns"),
    Output("tbl_last100", "data"),
    Input("zone_dd", "value"),
)
def update(zone_value):
    fig_bar = px.bar(x=[1, 2, 3], y=[3, 1, 2], title="Test bar")
    fig_line = px.line(x=[1, 2, 3], y=[1, 4, 2], title="Test line")

    return (
        html.Div("KPI CA OK"),
        html.Div("KPI N OK"),
        fig_bar,
        fig_line,
        [{"name": "A", "id": "A"}],
        [{"A": "test 1"}, {"A": "test 2"}]
    )


# ============================================================
# 6) RUN
# ============================================================

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
if __name__ == "__main__":
    app.run(debug=False)
