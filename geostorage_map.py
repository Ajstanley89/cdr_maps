from requests import get
import json
import pandas as pd
import geopandas as gpd
import numpy as np
import math
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import os

# folder holding all forestry cdr data
geostorage_path = 'data/geostorage'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data/label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})

# get percentage of area in storage window
geo_storage_area_df = pd.read_excel(f'{geostorage_path}/Counties_in_storage_2023Sept12.xlsx', dtype={'FIPS':str})
geo_storage_area_df = geo_storage_area_df.rename(columns={'FIPS':'GEOID'})
geo_storage_area_df['GEOID'] = geo_storage_area_df['GEOID'].apply(lambda x: str(x).zfill(5))
geo_storage_area_df['Percentage'] = pd.to_numeric(geo_storage_area_df['Percentage'], errors='coerce')

# geo storage potential
geo_storage_cdr_df = pd.read_excel(f'{geostorage_path}/Storage cost per county data Edna.xlsx', dtype={'ST_CNTY_CODE':str})
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

# load basalt
basalt_path = "data/Geostorage/Basalt.zip!/Basalt/basalt.shp"
basalt_gdf = gpd.read_file(basalt_path)
basalt_gdf = basalt_gdf.to_crs('WGS84')

# split into several polygons
exploded_basalt_gdf = basalt_gdf.explode()
# get the exterior coordinatates of all polygons
coord_seq = exploded_basalt_gdf.reset_index().geometry.apply(lambda poly: poly.exterior.coords)
# get lata and lons
lngs = [[coord[0] for coord in coords] for coords in coord_seq]
lats = [[coord[1] for coord in coords] for coords in coord_seq]


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
                    '<b>Storage Cost</b>: %{customdata[1]:,.2f} USD per Tonne CO<sub>2</sub><br>' +
                    '<b>Percent Land Area in Storage Window</b>: %{customdata[2]:,.1f}%<br>'
                    '<extra></extra>'))

for i, trace in enumerate(fig.data, 1):
    trace.update(coloraxis=f"coloraxis{i}")
    
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0},
                  coloraxis2={"colorbar": {"x": 0.50, 
                                           "len": 0.75, 
                                           "y": -0.3,
                                           'title':'USD per Tonne CO<sub>2</sub>',
                                           'orientation':'h',
                                           'titlefont':{'size':10},
                                           'tickfont':{'size':10}
                                           },
                                'colorscale':'greens_r',
                                'cmax':40,
                                'cmin':5.99})

# Add traces for basalt
fig.add_trace(go.Choropleth(geojson=json.loads(basalt_gdf.geometry.to_json()),
                               locations=[0],
                               colorscale=[[0, '#FF7F7F'], [1, '#FF7F7F']],
                               z=[1]))
"""
for lng, lat in zip(lngs, lats):
    fig.add_trace(go.Scattergeo(lat=lat, 
                                 lon=lng, 
                                 mode='lines', 
                                 fill='toself',
                                 line = {'color': '#FF7F7F',
                                         # 'alpha': 0.6
                                       },
                                hoverinfo = 'text',
                                text = 'Basalt<br>Cost Unknown',
                                name = 'Basalt',
                                legendgroup = 'Basalt',
                                showlegend = 'Basalt' not in {d.name for d in fig.data}))
"""
    
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
fig.update_coloraxes(colorbar_title_side='top')
fig.show()
fig.write_html('chapter_maps/geostorage_map.html')



