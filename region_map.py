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
county_fips_df = pd.read_csv('data\label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})
county_fips_df['GEO_ID'] = '0500000US' + county_fips_df['FIPS']

# map county names to regions
regions_df = pd.read_excel('data/Regions and SVI.xlsx', sheet_name='County_Region_Mapping', dtype={'FIPS': str, 'GEOID':str})
regions_df['GEOID'] = regions_df['GEOID'].apply(lambda x: str(x).zfill(5))
regions_df['FIPS'] = regions_df['FIPS'].apply(lambda x: str(x).zfill(5))

# read file taken from census. This should have Oglala 
counties_path = 'data\cb_2018_us_county_500k.zip!cb_2018_us_county_500k.shp'
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
    text = ['<br>'.join(l) for l in df.apply(lambda row: [f'{sm}: {x} {unit.strip("[]")}' for sm, x in zip(submethods, row)], axis=1).to_list()]

    # create total column for each method
    df[(method, unit, 'Total')] = df.loc[:, idx[method, unit, :]].sum(axis=1)
    # column for text
    df[(method, unit, 'Text')] = text
    return df

# create list of dfs for each cdr method
methods_dfs = [process_regional_methods(regions_df, method, unit) for method, unit in {(a, b) for a, b, c in regions_df.columns}]

def make_choro_trace(df, color_scale='blues'):
    """
    Takes a df and returns a plotly GO choropleth object
    """
    trace = go.Choropleth(
                        geojson=json.loads(regions_gdf.geometry.to_json()),
                        locationmode="geojson-id",
                        locations=df.index,
                        # featureidkey='properties.GEO_ID',
                        z=df.iloc[:, -1],
                        zauto=True,
                        coloraxis='coloraxis',
                        colorscale=color_scale,
                        customdata=df.reset_index().iloc[:, :-1],
                        hovertemplate=  '<b>Region</b>: %{customdata[0]}<br>' +
                                        f'<b>Regional CDR Potential</b>: %{z:,.0f} {df.columns.get_level_values(1)[0]}' +
                                        #'<b>Regional CDR Average Cost</b>: $%{customdata[1]:,.0f} per Million Tonnes CO<sub>2</sub><br>' +
                                        '%{text}'
                                        '<extra></extra>',
                        text = df['Text'])
    return trace

fig = go.Figure(make_choro_trace(bicrs_both_df, 'Viridis'))
fig.update_geos(scope='usa')
fig.update_layout(coloraxis_colorscale='Viridis')
"""
# Add locations bar chart
fig.add_trace(
    go.Bar(x=freq["x"][0:10],y=freq["Country"][0:10], marker=dict(color="crimson"), showlegend=False),
    row=1, col=2
)
"""

# Colorscales: Blackbody,Bluered,Blues,Cividis,Earth,Electric,Greens,Greys,Hot,Jet,Picnic,Portland,Rainbow,RdBu,Reds,Viridis,YlGnBu,YlOrRd.
# create buttons to filter between wet and dry
fig.update_layout(
    updatemenus=[
        dict(
            type="buttons",
            direction="right",
            x=0.7,
            y=1.2,
            active=0,
            buttons=[
                        dict(
                            label="Total Biomass",
                            method="update",
                            args=[{"z": [bicrs_both_df['Sum CO2 Removal Potential (Million tonnes CO2/year)']],
                                'locations': [bicrs_both_df['Region']],
                                    'customdata': [bicrs_both_df[['Region', 'Average  regional cost ($/tonne CO2)']].values.tolist()]
                                    },
                                    {"coloraxis.colorscale": 'Viridis' #[[0, '#EBD985'], [1, '#7DB28C']]
                                }],
                            ),
                        dict(
                            label="Wet Biomass Waste",
                            method="update",
                            args=[{"z": [bicrs_wet_df['Sum CO2 Removal Potential (Million tonnes CO2/year)']],
                                'locations': [bicrs_wet_df['Region']],
                                'customdata': [bicrs_wet_df[['Region', 'Average  regional cost ($/tonne CO2)']].values.tolist()]
                                    },
                                {"coloraxis.colorscale": 'Viridis' #[[0, '#FFFFFF'], [1, '#906E92']]
                                }],
                        ),
                        dict(
                            label="Low Moisture Biomass",
                            method="update",
                            args=[{"z": [bicrs_dry_df['Sum CO2 Removal Potential (Million tonnes CO2/year)']],
                                'locations': [bicrs_dry_df['Region']],
                                    'customdata': [bicrs_dry_df[['Region', 'Average  regional cost ($/tonne CO2)']].values.tolist()]
                                    },
                                    {"coloraxis.colorscale": 'Viridis' #[[0, '#EBD985'], [1, '#7DB28C']]
                                }],
                            ),

                    ] 
                )
            ],
        coloraxis={'colorbar': {'title':'Annual Carbon Removal<br>Potential in 2050'}},
        title={
        'text': "Zero cropland change biomass<br>optimal use of 90% of total biomass supply to minimize cost per tonne CO<sub>2</sub>e",
        'y':1,
        'x':0.5,
        'font':{'size':10},
        'xanchor': 'center',
        'yanchor': 'top',
        'yref': 'paper'
        }   
        )
fig.show()
fig.write_html('chapter_maps/bicrs_map.html')



