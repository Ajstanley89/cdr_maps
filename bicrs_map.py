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
bicrs_path = 'data/BiCRS CDR'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data\label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})
county_fips_df['GEO_ID'] = '0500000US' + county_fips_df['FIPS']

# map county names to regions
regions_df = pd.read_excel('data/Regions and SVI.xlsx', sheet_name='County_Region_Mapping', dtype={'FIPS': str, 'GEOID':str})
regions_df['GEOID'] = regions_df['GEOID'].apply(lambda x: str(x).zfill(5))
regions_df['FIPS'] = regions_df['FIPS'].apply(lambda x: str(x).zfill(5))

# read bicrs data
bicrs_wet_df = pd.read_excel(f'{bicrs_path}/20231205 Regional Summary.xlsx', sheet_name='Regional cost and CDR Wet only')
bicrs_dry_df = pd.read_excel(f'{bicrs_path}/20231205 Regional Summary.xlsx', sheet_name='Regional cost CDR Dry only')
bicrs_both_df = pd.read_excel(f'{bicrs_path}/20231205 Regional Summary.xlsx', sheet_name='Regional cost and CDR Wet + Dry')
bicrs_transport_df = pd.read_excel(f'{bicrs_path}/20231205 Regional Summary.xlsx', sheet_name='CO2 by transport mode')

# merge cdr dfs with region dfs
def process_bicrs(df):
    """
    Processes Bicrs Region Dfs

    Drops empty rows and fills other values forward
    """
    df = df.dropna(how='all')
    return df.ffill()

# Process all dfs
bicrs_wet_df = process_bicrs(bicrs_wet_df)
bicrs_dry_df = process_bicrs(bicrs_dry_df)
bicrs_both_df = process_bicrs(bicrs_both_df)

# read file taken from census. This should have Oglala 
counties_path = 'data\cb_2018_us_county_500k.zip!cb_2018_us_county_500k.shp'
census_gdf = gpd.read_file(counties_path)

# merge them together
census_gdf = census_gdf.merge(regions_df, left_on='GEOID', right_on='FIPS')

# combine regions into one polygon
regions_gdf = census_gdf[['Region', 'geometry']].dissolve(by='Region')

def make_choro_trace(df, color_scale):
    """
    Takes a df and returns a plotly GO choropleth object
    """
    print(df.columns)
    trace = go.Choropleth(
                        geojson=json.loads(regions_gdf.geometry.to_json()),
                        locationmode="geojson-id",
                        locations=df['Region'],
                        # featureidkey='properties.GEO_ID',
                        z=df['Sum CO2 Removal Potential (Million tonnes CO2/year)'],
                        zauto=True,
                        coloraxis='coloraxis',
                        # colorscale=color_scale,
                        customdata=df[['Region', 'Average  regional cost ($/tonne CO2)']],
                        hovertemplate=  '<b>Region</b>: %{customdata[0]}<br>' +
                                        '<b>Regional CDR Potential</b>: %{z:,.0f} Million Tonnes CO<sub>2</sub> per Year<br>' +
                                        '<b>Regional CDR Average Cost</b>: $%{customdata[1]:,.0f} per Million Tonnes CO<sub>2</sub><br>' +
                                        '<extra></extra>')
    return trace

def make_bar_trace(df):
    """
    Takes a bicrs region df, sorts values, then plots a staced bar chart
    """
    df = df.sort_values(by=['Sum CO2 Removal Potential (Million tonnes CO2/year)', 'CO2 Removal Potential (tonne CO2/year)'], ascending=[False, False])

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



