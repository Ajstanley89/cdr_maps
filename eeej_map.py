from itertools import count
from xml.etree.ElementPath import prepare_self
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
eeej_path = 'data/EEEJ'
def create_eeej_path(path):
    return "/".join([eeej_path, path])

# data from census linking county name and fips
county_fips_df = pd.read_csv('data\label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})

# read file taken from census. This should have Oglala 
counties_path = 'data\cb_2018_us_county_500k.zip!cb_2018_us_county_500k.shp'
census_gdf = gpd.read_file(counties_path, dtypes={'GEOID':str})
census_gdf = census_gdf.set_index('GEOID')

# load index to rule them all data
cdr_scores_df = pd.read_csv(create_eeej_path('percentile_ranking_all_methods.csv'), dtype={'GEOID':str})
# rename 'DAC' to 'DACS'
cdr_scores_df.loc[cdr_scores_df['Highest CDR Method']=='DAC', 'Highest CDR Method'] = 'DACS'

"""
# some data like AK and HI wasn't included in the cdr data. Fill those values with the minimum score as BiCRS
cdr_scores_df = cdr_scores_df.merge(county_fips_df, left_on='GEOID', right_on='FIPS', how='outer')
cdr_scores_df['Highest CDR Method'] = cdr_scores_df['Highest CDR Method'].fillna('BiCRS')
cdr_scores_df['Max EEEJ weighted CDR score'] = cdr_scores_df['Max EEEJ weighted CDR score'].fillna(.01)
"""


# define function to read all trifecta data
def process_trifecta(path, cdr_method):
    df = pd.read_excel(path, sheet_name=0, dtype={'GEOID':str})
    # keep only relevant columns
    df = df.loc[:,['GEOID', 'County, State', 'EEEJ Avg Index', 'SVI']]
    # calculate percentile rank of eeej
    df['EEEJ Percentile Rank'] = df['EEEJ Avg Index'].rank(pct=True)
    df['CDR Method'] = cdr_method
    return df

# dictionary linking cdr method to its data
methods_paths = {'Forests': create_eeej_path('trifecta/forestry_trifecta_v3.xlsx'), 
                 'Soils': create_eeej_path('trifecta/soils_trifecta_v2.xlsx'), 
                 'BiCRS': create_eeej_path('trifecta/bicrs_trifecta_v5.xlsx'),
                 'DACS': create_eeej_path('trifecta/sorbent_dac_trifecta_v2.xlsx')}

# dictionary processing all eeej dfs
eeej_dfs = [process_trifecta(path, key) for key, path in methods_paths.items()]

eeej_df = pd.concat(eeej_dfs)
# merge cdr score with underlying EEEJ values
cdr_scores_df = cdr_scores_df.merge(eeej_df, left_on=['GEOID', 'Highest CDR Method'], right_on=['GEOID', 'CDR Method'])

# dictionary showing color scheme
color_dict = {'Forests': [[0, '#FFFFFF'], [1, '#0c6533']], 
                 'Soils': [[0, '#FFFFFF'], [1, '#e58f17']], 
                 'BiCRS': [[0, '#FFFFFF'], [1, '#703b9b']],
                 'DACS': [[0, '#FFFFFF'], [1, '#2a58a8']]}

fontsize=10

# make choropleth for soils map
fig = go.Figure()

print(cdr_scores_df[cdr_scores_df['Highest CDR Method']=='DACS'])
print(cdr_scores_df['Highest CDR Method'].value_counts())
# create a trace for each cdr method
for i, method in enumerate(methods_paths.keys(), 1):
    # Filter for method
    df = cdr_scores_df.loc[cdr_scores_df['Highest CDR Method'] == method]

    # create map
    fig.add_trace(trace=go.Choropleth(
        geojson=json.loads(census_gdf.geometry.to_json()),
        locations=df['GEOID'],
        z=df['Max EEEJ weighted CDR score'],
        zauto= True,
        coloraxis= f'coloraxis{i}',
        # colorscale=color_dict.get(method, 'Viridis'),
        customdata=df[['Highest CDR Method', 'County, State_x', 'EEEJ Percentile Rank', 'SVI']],
        hovertemplate='<b>Top Practice</b>: %{customdata[0]}<br>' +
                        '<b>County</b>: %{customdata[1]}<br>' +
                        '<b>Equity Weighted CDR Score</b>: %{z:,.2f}<br>'
                        '<b>EEEJ Opportunity Percentile</b>: %{customdata[2]:,.2f}<br>' +
                        '<b>Social Vulnerability Index</b>: %{customdata[3]:,.2f}<br>' +
                        '<extra></extra>'))
    
    fig.update_layout({f'coloraxis{i}':{'colorscale':color_dict.get(method, 'Viridis'),
                                        'colorbar': {"x": 0.9,
                                                    "len": 0.2,
                                                     "y": 1 - (0.2 * i),
                                                    'title': method,
                                                    'orientation':'v',
                                                    'titlefont':{'size':fontsize},
                                                    'tickfont':{'size':fontsize}},
                                        'cmax': 1,
                                        'cmin': 0
                                        }                   
                        })
    
    # Get rid of color bar. All color bars overlap right now, so it looks neater without them
    # fig.update_traces(showscale=False)

fig.update_geos(scope='usa')
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

"""# assign each trace to new color axis
for i, trace in enumerate(fig.data, 1):
    trace.update(coloraxis=f"coloraxis{i}")"""

# Add color scales
fig.update_layout(
    title={
        'text': "EEEJ Weighted CDR Index",
        'y':0.95,
        'x':0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'yref': 'paper'
        }),
""" 
# coloraxis={"colorbar": {"x": -0.2, "len": 0.5, "y": 0.8}},
    coloraxis1={
        "colorbar": {
            "x": 0.9,
            "len": 0.2,
            "y": 0.8,
            'title':'Forests',
            'orientation':'v',
            'titlefont':{'size':fontsize},
            'tickfont':{'size':fontsize}},
        "colorscale":color_dict.get('Forests'),
        'cmax':1,
        'cmin': 0
    },
    coloraxis2={
        "colorbar": {"x": 0.9, 
                     "len": 0.2, 
                     "y": 0.6, 
                     'title':'Soils',
                     'orientation':'v',
                     'titlefont':{'size':fontsize},
                     'tickfont':{'size':fontsize}},
        "colorscale":color_dict.get('Soils', 'Viridis'),
        'cmax': 1,
        'cmin': 0
    },
    coloraxis3={
        "colorbar": {"x": 0.9, 
                     "len": 0.2, 
                     "y": 0.4,
                     'title':'BiCRS',
                     'orientation':'v',
                     'titlefont':{'size':fontsize},
                     'tickfont':{'size':fontsize}},
        "colorscale": color_dict.get('BiCRS', 'Viridis'),
        'cmax': 1,
        'cmin': 0
            },
    coloraxis={
        "colorbar": {"x": 0.9, 
                     "len": 0.2, 
                     "y": 0.2,
                     'title':'DACS',
                     'orientation':'v',
                     'titlefont':{'size':fontsize},
                     'tickfont':{'size':fontsize}},
        "colorscale": color_dict.get('DACS', 'Viridis'),
        'cmax': 1,
        'cmin': 0
            })
"""

fig.show()
fig.write_html('chapter_maps/eeej_map.html', full_html=False, include_plotlyjs='cdn')



