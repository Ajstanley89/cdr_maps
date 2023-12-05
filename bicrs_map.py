from heapq import merge
from wsgiref.util import shift_path_info
from requests import get
import json
import pandas as pd
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
bicrs_wet_df = pd.read_excel(f'{bicrs_path}\Regional Summary.xlsx', sheet_name=0)
bicrs_dry_df = pd.read_excel(f'{bicrs_path}\Regional Summary.xlsx', sheet_name=1)
bicrs_transport_df = pd.read_excel(f'{bicrs_path}\Regional Summary.xlsx', sheet_name=2)

# drop empty rows
bicrs_wet_df = bicrs_wet_df.dropna(how='all')
bicrs_dry_df = bicrs_dry_df.dropna(how='all')

# fill sum and cost values forward
bicrs_wet_df = bicrs_wet_df.ffill()
bicrs_dry_df = bicrs_dry_df.ffill()

# dict to rename columns
bicrs_titles = {title: 'Regional ' + title for title in ['CO2 Removal Potential (tonne CO2/year)', '$/tonne CO2 (per technology)', 'Sum CO2 Removal Potential (Million tonnes CO2/year)']}

# merge cdr dfs with region dfs
def merge_regions(df, on='Region'):
    """
    Merge a bicrs df on region
    """
    df = df.merge(regions_df, on=on)
    df = df.merge(county_fips_df, left_on='GEOID', right_on='FIPS')
    # Rename Columns to make clear that the totals are for the entire region
    return df.rename(columns=bicrs_titles)

bicrs_wet_county_df = merge_regions(bicrs_wet_df)
bicrs_dry_county_df = merge_regions(bicrs_dry_df)

# geo json file
from urllib.request import urlopen
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

# make subplots for bicrs data
# Use a button to filter between dry and wet wastes
"""fig = make_subplots(
                    rows=1, cols=2,
                    # column_widths=[0.6, 0.4],
                    # row_heights=[0.4, 0.6],
                    specs=[[{"type": "choropleth"}, {"type": "bar"}]],
                    subplot_titles=['CDR Potential by Region', 'CDR Potential by Technology']
                    )
"""
def make_choro_trace(df, color_scale):
    """
    Takes a df and returns a plotly GO choropleth object
    """
    print(df.columns)
    trace = go.Choropleth(
                        geojson=counties,
                        locationmode="geojson-id",
                        locations=df['GEO_ID'],
                        featureidkey='properties.GEO_ID',
                        z=df['Regional Sum CO2 Removal Potential (Million tonnes CO2/year)'],
                        zauto=True,
                        coloraxis='coloraxis',
                        # colorscale=color_scale,
                        customdata=df[['County, State', 'Region', 'Average  regional cost ($/tonne CO2)']],
                        hovertemplate='<b>County</b>: %{customdata[0]}<br>' +
                                        '<b>Region</b>: %{customdata[1]}<br>' +
                                        '<b>Regional CDR Potential</b>: %{z:,.0f} Million Tonnes CO<sub>2</sub> per Year<br>' +
                                        '<b>Regional CDR Average Cost</b>: %{customdata[2]:,.0f} USD per Million Tonnes CO<sub>2</sub><br>' +
                                        '<extra></extra>')
    return trace

def make_bar_trace(df):
    """
    Takes a bicrs region df, sorts values, then plots a staced bar chart
    """
    df = df.sort_values(by=['Sum CO2 Removal Potential (Million tonnes CO2/year)', 'CO2 Removal Potential (tonne CO2/year)'], ascending=[False, False])

fig = go.Figure(make_choro_trace(bicrs_wet_county_df, 'Purpor'))
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
                            label="Wet Wastestreams",
                            method="update",
                            args=[{"z": [bicrs_wet_county_df['Regional Sum CO2 Removal Potential (Million tonnes CO2/year)']],
                                'locations': [bicrs_wet_county_df['GEO_ID']],
                                'customdata': [bicrs_wet_county_df[['County, State', 'Region', 'Average  regional cost ($/tonne CO2)']].values.tolist()]
                                    },
                                {"coloraxis.colorscale": 'Viridis' #[[0, '#FFFFFF'], [1, '#906E92']]
                                }],
                        ),
                        dict(
                            label="Dry Wastestreams",
                            method="update",
                            args=[{"z": [bicrs_dry_county_df['Regional Sum CO2 Removal Potential (Million tonnes CO2/year)']],
                                'locations': [bicrs_dry_county_df['GEO_ID']],
                                    'customdata': [bicrs_dry_county_df[['County, State', 'Region', 'Average  regional cost ($/tonne CO2)']].values.tolist()]
                                    },
                                    {"coloraxis.colorscale": 'Cividis' #[[0, '#EBD985'], [1, '#7DB28C']]
                                }],
                            ),
                    ] 
                )
            ],
        coloraxis={'colorbar': {'title':'Million Tonnes CO<sub>2</sub><br>Removed by 2050'}}   
        )
fig.show()
fig.write_html('chapter_maps/bicrs_map.html')



