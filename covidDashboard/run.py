#### Covid Dashboard for Malaysia
#### Howard Gan
#### 2020-07-03

import pandas as pd
import numpy as np
import datetime
import dateutil.parser
from plotnine import *
import plotly_express as px
import plotly.graph_objs as go
import matplotlib.pyplot as plt
import plotly.io as pio
import seaborn as sns
import sqlite3
import requests
import json
import os

import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

# %% Set defaults here
os.chdir(r"C:\Users\HowardG\Google Drive\pythonProjects\development\covidDashboard")
pio.templates.default = "simple_white"

# %% Load in data from the database
conn = sqlite3.connect("malaysia_covid.db")
req = pd.read_sql("SELECT * from malaysia_covid_data", con=conn).drop("index", axis=1)
conn.commit()
conn.close()

# If the gap between the latest date and now is two days or more, then the data has to be refreshed
nowDate = datetime.datetime.now()
latestDate = dateutil.parser.parse(req.Date.values[-1])

refreshRule = nowDate.day - latestDate.day >= 2

# %% Load in the data from the API
if refreshRule:
    # request the website using requests
    req = requests.get("https://api.covid19api.com/all")
    req = req.json()

# %% Get only the malaysian data from the dataframe
# Convert the json into a pandas dataframe
df = pd.DataFrame(req)
df = df[df["Country"] == "Malaysia"]
df = df.reset_index(drop=True)


#%% Save the data into the database
def update_database(df):
    # Start an SQLite3 connection
    conn = sqlite3.connect("malaysia_covid.db")
    # Use pandas to_sql to save and over-write the data
    df.to_sql(name="malaysia_covid_data", con=conn, if_exists="replace")
    # Commit and close the connection
    conn.commit()
    conn.close()


update_database(df)


# %% Produce visualisations for the data
plotData = df[["Country", "Confirmed", "Deaths", "Recovered", "Active", "Date"]].drop(
    154  # Erroneous data in this row
)

# Produce a plot to show the cumulative situation
pData = plotData.drop("Country", axis=1).melt("Date")
plot_cumulative = px.line(
    data_frame=pData,
    x="Date",
    y="value",
    facet_col="variable",
    range_y=[min(pData.value), max(pData.value)]
    # title="Cumulative plots",
)
plot_cumulative.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
plot_cumulative.update_yaxes(
    title_text="",
    matches="y",
    fixedrange=True,
    range=[min(pData.value), max(pData.value)],
)
plot_cumulative.update_layout(hovermode="x")


# %% Perform diff on the plotData dataframes to see daily changes
plotData_diff = plotData.copy()

plotData_diff["New confirmed cases"] = plotData_diff.Confirmed.diff()
plotData_diff["Daily deaths"] = plotData_diff.Deaths.diff()
plotData_diff["Daily recoveries"] = plotData_diff.Recovered.diff()
plotData_diff["Change in active cases today"] = plotData_diff.Active.diff()


# %% Process the data further for visualisation
plotData_trans = plotData_diff.copy()

# Add 7 day moving averages
plotData_trans["New confirmed cases (7 day MA)"] = (
    plotData_trans["New confirmed cases"].rolling(7).mean()
)
plotData_trans["Daily deaths (7 day MA)"] = (
    plotData_trans["Daily deaths"].rolling(7).mean()
)
plotData_trans["Daily recoveries (7 day MA)"] = (
    plotData_trans["Daily recoveries"].rolling(7).mean()
)

# %% Make a plot for new cases
plot_new_cases = go.Figure()
plot_new_cases.add_trace(
    go.Scatter(
        x=plotData_trans.Date,
        y=plotData_trans["New confirmed cases"],
        name="New confirmed cases",
    )
)
plot_new_cases.add_trace(
    go.Scatter(
        x=plotData_trans.Date,
        y=plotData_trans["New confirmed cases (7 day MA)"],
        name="New confirmed cases (7 day MA)",
        visible="legendonly",
    )
)
plot_new_cases.update_layout(legend_orientation="h", title="New confirmed cases")
plot_new_cases.layout.yaxis.fixedrange = True

# %% Make a plot for new recoveries
# y-limits for deaths and recoveries
ylim = [
    0,
    max([plotData_diff["Daily deaths"].max(), plotData_diff["Daily recoveries"].max()]),
]

# Make the plots
plot_new_recovered = go.Figure()
plot_new_recovered.add_trace(
    go.Scatter(
        x=plotData_trans.Date,
        y=plotData_trans["Daily recoveries"],
        name="Daily recoveries",
    )
)
plot_new_recovered.add_trace(
    go.Scatter(
        x=plotData_trans.Date,
        y=plotData_trans["Daily recoveries (7 day MA)"],
        name="Daily recoveries (7 day MA)",
        visible="legendonly",
    )
)
plot_new_recovered.update_layout(legend_orientation="h", title="Daily recoveries")
plot_new_recovered.layout.yaxis.fixedrange = True

# %% Make a plot for new deaths
plot_new_deaths = go.Figure()
plot_new_deaths.add_trace(
    go.Scatter(
        x=plotData_trans.Date, y=plotData_trans["Daily deaths"], name="Daily deaths",
    )
)
plot_new_deaths.add_trace(
    go.Scatter(
        x=plotData_trans.Date,
        y=plotData_trans["Daily deaths (7 day MA)"],
        name="Daily deaths (7 day MA)",
        visible="legendonly",
    )
)
plot_new_deaths.update_layout(legend_orientation="h", title="Daily deaths")
plot_new_deaths.layout.yaxis.fixedrange = True

# %% Call in the function that generates a table in html
def generate_table(dataframe, max_rows=26):
    return html.Table(
        # Header
        [html.Tr([html.Th(col) for col in dataframe.columns])]
        +
        # Body
        [
            html.Tr([html.Td(dataframe.iloc[i][col]) for col in dataframe.columns])
            for i in range(min(len(dataframe), max_rows))
        ]
    )


# %% Make strings to summarise the latest data in a table/df
summary_df = pd.DataFrame(
    (
        plotData_trans.drop(
            [
                "Country",
                "New confirmed cases (7 day MA)",
                "Daily deaths (7 day MA)",
                "Daily recoveries (7 day MA)",
            ],
            axis=1,
        )
        .rename(
            columns={"Daily deaths": "New deaths", "Daily recoveries": "New recoveries"}
        )
        .iloc[-1,]
    )
).reset_index()

summary_df = summary_df.rename(
    columns={summary_df.columns[0]: "Stat", summary_df.columns[1]: "Malaysia"}
)

summary_df.iloc[4][1] = summary_df.iloc[4].values[1][0:10]

# Make a plotly table object
summary_table = go.Figure(
    data=[
        go.Table(
            header=dict(
                values=list(summary_df.columns),
                # fill_color="paleturquoise",
                align="left",
            ),
            cells=dict(
                values=[summary_df.Stat, summary_df.Malaysia],
                # fill_color="lavender",
                align="left",
            ),
        )
    ]  # ,
    # template = "darkly"
)

# Update the height of the plotly object / table
summary_table.update_layout(height=400, width=600)


# %% Initialise the app
app = dash.Dash(
    __name__,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ],
    external_stylesheets=[dbc.themes.DARKLY],
)
server = app.server

# %% Develop the UI/layout
app.layout = html.Div(
    children=[
        html.H1(children="Malaysia Coronavirus Dashboard"),
        html.Div(
            children="""
        Data obtained from  https://api.covid19api.com/
    """
        ),
        html.Br(),
        html.H3(children="The latest data at a glance..."),
        dcc.Graph(id="summary_table", figure=summary_table),
        html.Br(),
        html.H3(children="Cumulative plots"),
        dcc.Graph(id="plot_cumulative", figure=plot_cumulative),
        html.Br(),
        html.H3(children="Daily plots"),
        dcc.Graph(id="plot_new_cases", figure=plot_new_cases),
        html.Br(),
        dcc.Graph(id="plot_new_recovered", figure=plot_new_recovered),
        html.Br(),
        dcc.Graph(id="plot_new_deaths", figure=plot_new_deaths),
    ]
)

# %% Write callbacks


# %% Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
