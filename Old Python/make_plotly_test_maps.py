from requests import get
import json
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output
import os

# try building dahboard on DAC data for illustrative purposes
eeej_path = 'data\dac_indices.xlsx'
dac_cdr_path = 'data\Sorbent_HP_2050_Cty_wtavg_9.csv'
dac_eeej_df = pd.read_excel(eeej_path, dtype={'GEOID':'str'})
dac_cdr_df = pd.read_csv(dac_cdr_path, dtype={'county':'str'})

# geo json file
from urllib.request import urlopen
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)


# make choropleth for dac map
dac_map_fig = px.choropleth_mapbox(dac_cdr_df, geojson=counties, locations='county', color='county_DACcap_tpa',
                           color_continuous_scale="Viridis",
                           range_color=(dac_cdr_df['county_DACcap_tpa'].min(), dac_cdr_df['county_DACcap_tpa'].max()),
                           mapbox_style="carto-positron",
                           zoom=2, center = {"lat": 37.0902, "lon": -95.7129},
                           opacity=0.5,
                          )
dac_map_fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
dac_map_fig.write_html('dac_map.html')

# make chloropleth for EEEJ map
eeej_map_fig = px.choropleth_mapbox(dac_eeej_df, geojson=counties, locations='GEOID', color='EEEJ Avg Index',
                           color_continuous_scale="dense",
                           range_color=(dac_eeej_df['EEEJ Avg Index'].min(), dac_eeej_df['EEEJ Avg Index'].max()),
                           mapbox_style="carto-positron",
                           zoom=2, center = {"lat": 37.0902, "lon": -95.7129},
                           opacity=0.5,
                          )
eeej_map_fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
eeej_map_fig.write_html('eeej_map.html')



