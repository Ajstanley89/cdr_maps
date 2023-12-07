from heapq import merge
from wsgiref.util import shift_path_info
from requests import get
import json
import pandas as pd
import geopandas as gpd
import numpy as np
import math
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, Input, Output
import os

# folder holding all forestry cdr data
regions_path = 'data/Regional Analysis'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data/label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})
county_fips_df['GEO_ID'] = '0500000US' + county_fips_df['FIPS']

# map county names to regions
regions_df = pd.read_excel('data/Regions and SVI.xlsx', sheet_name='County_Region_Mapping', dtype={'FIPS': str, 'GEOID':str})
regions_df['GEOID'] = regions_df['GEOID'].apply(lambda x: str(x).zfill(5))
regions_df['FIPS'] = regions_df['FIPS'].apply(lambda x: str(x).zfill(5))

# read file taken from census. This should have Oglala 
counties_path = 'data/cb_2018_us_county_20m.zip!cb_2018_us_county_20m.shp'
census_gdf = gpd.read_file(counties_path)

# merge them together
census_gdf = census_gdf.merge(regions_df, left_on='GEOID', right_on='FIPS')

# combine regions into one polygon
regions_gdf = census_gdf[['Region', 'geometry']].dissolve(by='Region')

# read regions data
regions_path = 'data/Regional Analysis'
regions_df = pd.read_csv(f'{regions_path}/R2R Regions - Summary Table.csv', header=[0,1,2], index_col=0)

# loop through each method and process data
idx = pd.IndexSlice

def process_regional_methods(regions_df, method, unit):
    """
    Takes the method and unit from the regional df index, calculates the regional cdr for that method, then returns a df of that method
    """
    df = regions_df.loc[:, idx[method, unit, :]]
    # fill nan with 0
    df = df.fillna(0)

    # get column names for submethods
    submethods = list(df.columns.get_level_values(-1))
    # Join Text for tooltip formating. Should be: Submethod: cdr value unit<br>...
    text = ['<br>'.join(l) for l in df.apply(lambda row: [f'<b>{sm}</b>: {x} {unit.strip("[]")}' for sm, x in zip(submethods, row)], axis=1).to_list()]

    # create total column for each method
    df[(method, unit, 'Total')] = df.loc[:, idx[method, unit, :]].sum(axis=1)
    # column for text
    df[(method, unit, 'Text')] = text
    return df

# create list of dfs for each cdr method
methods_dfs = [process_regional_methods(regions_df, method, unit) for method, unit in {(a, b) for a, b, c in regions_df.columns}]

def make_choro_trace(df, trace_count, color_scale='Reds'):
    """
    Takes a df and returns a plotly GO choropleth object

    trace_count is the index of the trace. It sets the first trace to visible, and the rest not visible
    """
    # get unit of measure from column index
    unit = df.columns.get_level_values(1)[0].strip('[]')
    # set graph visibility
    visible = True if trace_count == 0 else False
    # drop multi index columns
    df.columns = df.columns.droplevel([0,1])
    df = df.reset_index()
    trace = go.Choropleth(
                        geojson=json.loads(regions_gdf.geometry.to_json()),
                        locationmode="geojson-id",
                        locations=df['index'],
                        # featureidkey='id',
                        z=df['Total'],
                        zauto=True,
                        # coloraxis=f'coloraxis{i+1}',
                        colorscale=color_scale,
                        customdata= df[['index']],
                        hovertemplate=  '<b>Region</b>: %{customdata[0]}<br>' +
                                        '<b>Regional CDR Potential</b>: %{z:,.0f} ' + unit + '<br>' +
                                        '%{text}' +
                                        '<extra></extra>',
                        text = df['Text'],
                        visible = visible
    )
    return trace

fig = go.Figure()

# make plots
for i, df in enumerate(methods_dfs):
    fig.add_trace(make_choro_trace(df, i))
    # print(fig.data)

fig.update_geos(scope='usa')


# Colorscales: Blackbody,Bluered,Blues,Cividis,Earth,Electric,Greens,Greys,Hot,Jet,Picnic,Portland,Rainbow,RdBu,Reds,Viridis,YlGnBu,YlOrRd.
# create buttons to filter between wet and dry
  
fig.show()
fig.write_html('chapter_maps/regional_map.html')



