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

    dff = df_base.copy()

    # Filtre multi-zones
    if zone_value and len(zone_value) > 0:
        dff = dff[dff[zone_col].astype(str).isin([str(z) for z in zone_value])]

    # Sécurité si vide
    if dff.empty:
        empty_bar = px.bar(title="Frequence des 10 meilleures ventes")
        empty_line = px.line(title="Evolution du chiffre d'affaire par semaine")
        return (
            kpi_block("—", 0, 0, is_money=True),
            kpi_block("—", 0, 0, is_money=False),
            empty_bar,
            empty_line,
            [],
            []
        )

    # Mois courant
    current_month = int(dff["Month"].max())

    # KPI CA
    m1, ca_cur, ca_delta = indicateur_du_mois(
        dff, current_month=current_month, freq=False, abbr=False
    )
    kpi_ca = kpi_block(m1, ca_cur, ca_delta, is_money=True)

    # KPI ventes
    m2, n_cur, n_delta = indicateur_du_mois(
        dff, current_month=current_month, freq=True, abbr=False
    )
    kpi_n = kpi_block(m2, n_cur, n_delta, is_money=False)

    # BAR TOP10
        # BAR TOP10
    top_df = frequence_meilleure_vente(dff, top=10)

    # Sécurité si jamais top_df est vide
    if top_df.empty:
        fig_bar = px.bar(title="Frequence des 10 meilleures ventes")
    else:
        # Orden total de las catégories de la plus fréquente à la moins fréquente
        order = (
            top_df.groupby("Product_Category")["Frequence"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )

        fig_bar = px.bar(
            top_df,
            x="Frequence",
            y="Product_Category",
            color="Gender",
            orientation="h",
            title="Frequence des 10 meilleures ventes",
            category_orders={"Product_Category": order},
            color_discrete_map={"F": "#636EFA", "M": "#EF553B", "NA": "#00CC96"},
        )

        fig_bar.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=50, b=10),
            legend_title_text="Sexe",
            barmode="group"
        )

        fig_bar.update_xaxes(title_text="Total vente")
        fig_bar.update_yaxes(
            title_text="Categorie du produit"
        )
    # LINE WEEKLY CA
    weekly = (
        dff.set_index("Transaction_Date")["Total_price"]
        .resample("W")
        .sum()
        .reset_index()
        .rename(columns={
            "Transaction_Date": "Semaine",
            "Total_price": "Chiffre d'affaire"
        })
    )

    fig_line = px.line(
        weekly,
        x="Semaine",
        y="Chiffre d'affaire",
        title="Evolution du chiffre d'affaire par semaine",
    )
    fig_line.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=50, b=10)
    )
    fig_line.update_xaxes(title_text="Semaine")
    fig_line.update_yaxes(title_text="Chiffre d'affaire")

    # TABLE last 100
    last100 = dff.sort_values("Transaction_Date", ascending=False).head(100).copy()
    last100["Transaction_Date"] = last100["Transaction_Date"].dt.strftime("%Y-%m-%d")

    show_cols = [
        "Transaction_Date", "Gender", "Location", "Product_Category",
        "Quantity", "Avg_Price", "Discount_pct"
    ]
    tbl = last100[show_cols]

    columns = [
        {"name": "Date" if c == "Transaction_Date" else c.replace("_", " "), "id": c}
        for c in tbl.columns
    ]
    data = tbl.to_dict("records")

    return kpi_ca, kpi_n, fig_bar, fig_line, columns, data

# ============================================================
# 6) RUN
# ============================================================

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
if __name__ == "__main__":
    app.run(debug=False)
