from requests import get
import json
import pandas as pd
import numpy as np
import math
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import os

# folder holding all forestry cdr data
geostorage_path = 'data\geostorage'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data\label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})

# get percentage of area in storage window
geo_storage_area_df = pd.read_excel(f'{geostorage_path}\Counties_in_storage_2023Sept12.xlsx', dtype={'FIPS':str})
geo_storage_area_df = geo_storage_area_df.rename(columns={'FIPS':'GEOID'})
geo_storage_area_df['GEOID'] = geo_storage_area_df['GEOID'].apply(lambda x: str(x).zfill(5))
geo_storage_area_df['Percentage'] = pd.to_numeric(geo_storage_area_df['Percentage'], errors='coerce')

# geo storage potential
geo_storage_cdr_df = pd.read_excel(f'{geostorage_path}\Storage cost per county data Edna.xlsx', dtype={'ST_CNTY_CODE':str})
geo_storage_cdr_df = geo_storage_cdr_df.rename(columns={'ST_CNTY_CODE':'GEOID'})
geo_storage_cdr_df['GEOID'] = geo_storage_cdr_df['GEOID'].apply(lambda x: str(x).zfill(5))
geo_storage_cdr_df['GEO_ID'] = '0500000US' + geo_storage_cdr_df['GEOID']
geo_storage_cdr_df['Ton CO2 per USD'] = geo_storage_cdr_df['StorageCost_USDperTonCO2']**-1
geo_storage_cdr_df['Ton CO2 per USD per Area'] = geo_storage_cdr_df['Ton CO2 per USD'] / geo_storage_cdr_df['GIS_ACRES']
geo_storage_cdr_df = geo_storage_cdr_df.dropna()
# Rename cost to something pretty
cost_col = 'Total Storage Cost (USD per Tonne CO2)'
geo_storage_cdr_df = geo_storage_cdr_df.rename(columns={'StorageCost_USDperTonCO2':cost_col})

# only use areas with >50% in storage window
geo_storage_cdr_df = geo_storage_cdr_df.merge(geo_storage_area_df.loc[geo_storage_area_df['Percentage'] > 50], on='GEOID')

# merge to get county state names
geo_storage_cdr_df = geo_storage_cdr_df.merge(county_fips_df, left_on='GEOID', right_on='FIPS')

print(geo_storage_cdr_df.columns)
# geo json file
from urllib.request import urlopen
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

# make choropleth for soils map
fig = go.Figure(go.Choropleth())
fig.update_geos(scope='usa')

# geostorage map only needs one trace
fig.add_trace(trace=go.Choropleth(
    geojson=counties,
    locationmode="geojson-id",
    locations=geo_storage_cdr_df['GEO_ID'],
    featureidkey='properties.GEO_ID',
    z=geo_storage_cdr_df[cost_col],
    zmax=40, # geo_storage_cdr_df[cost_col].quantile(.95),
    zmin=5.99,# geo_storage_cdr_df[cost_col].quantile(.05),
    colorscale='greens_r',
    customdata=geo_storage_cdr_df[['County, State', cost_col, 'Percentage']],
    hovertemplate='<b>County</b>: %{customdata[0]}<br>' +
                    '<b>Storage Cost</b>: %{customdata[1]:,.2f} USD per Tonne CO2<br>' +
                    '<b>Percent in Storage Window</b>: %{customdata[2]:,.1f}%<br>'
                    '<extra></extra>'))

# Get rid of color bar. All color bars overlap right now, so it looks neater without them
fig.update_traces(showscale=False)
    
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

fig.show()
fig.write_html('chapter_maps/geostorage_map.html')



