from heapq import merge
from pydoc import ErrorDuringImport
from turtle import color
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
import random

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

# colors for regions
colors_df = pd.read_excel('data/Regions and SVI.xlsx', sheet_name='RGB', dtype={'Hex Color #': str})
colors_df['Hex Color #'] = '#' + colors_df['Hex Color #']
colors_set = colors_df['Hex Color #'].to_list()

# copy pasta from https://towardsdatascience.com/discrete-colour-scale-in-plotly-python-26f2d6e21c77
def generateDiscreteColourScale(colour_set):
    #colour set is a list of lists
    colour_output = []
    num_colours = len(colour_set)
    divisions = 1./num_colours
    c_index = 0.
    # Loop over the colour set
    for cset in colour_set:
        num_subs = len(cset)
        sub_divisions = divisions/num_subs
        # Loop over the sub colours in this set
        for subcset in cset:
            colour_output.append((c_index,subcset))
            colour_output.append((c_index + sub_divisions-
                .001,subcset))
            c_index = c_index + sub_divisions
    colour_output[-1]=(1,colour_output[-1][1])
    return colour_output

colors = generateDiscreteColourScale(colors_set)

# read file taken from census. This should have Oglala 
counties_path = 'data/cb_2018_us_county_5m.zip!cb_2018_us_county_5m.shp'
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

# def process_regional_methods(regions_df, method, unit):
#     """
#     Takes the method and unit from the regional df index, calculates the regional cdr for that method, then returns a df of that method
#     """
#     print(method)
#     df = regions_df.loc[:, idx[method, unit, :]]
#     # fill nan with 0
#     df = df.fillna(0)

#     # get column names for submethods
#     submethods = list(df.columns.get_level_values(-1))
#     # Join Text for tooltip formating. Should be: Submethod: cdr value unit<br>...
#     text = ['<br>'.join(l) for l in df.apply(lambda row: [f'<b>{sm}</b>: {x} {unit.strip("[]")}' for sm, x in zip(submethods, row)], axis=1).to_list()]

#     # create total column for each method
#     df[(method, unit, 'Total')] = df.loc[:, idx[method, unit, :]].sum(axis=1)
#     # column for text
#     df[(method, unit, 'Text')] = text
#     return df

def find_top_two(regions_df):
    max1=regions_df.max(axis=1)
    maxcolum1=regions_df.idxmax(axis=1)
    
    max2 = regions_df.replace(np.array(regions_df.max(axis=1)),0).max(axis=1)
    maxcolum2=regions_df.replace(np.array(regions_df.max(axis=1)),0).idxmax(axis=1)
    
    return pd.DataFrame({ 'max1': max1, 'max2': max2 ,'maxcol1':maxcolum1,'maxcol2':maxcolum2 })

# get list of unique methods + their units
methods_units = regions_df.columns.droplevel(-1).unique()
# create list of dfs for each cdr method
#methods_dfs = [process_regional_methods(regions_df, method, unit) for method, unit in methods_units] # {(a, b) for a, b, c in regions_df.columns}]

#create new data frame with top 2 methods for each region
regions_top2_df = find_top_two(regions_df)


def make_choro_trace(df, region, color_scale='Rainbow'):
    """
    Takes a df and returns a plotly GO choropleth object

    trace_count is the index of the trace. It sets the first trace to visible, and the rest not visible
    """
    # # Get CDR method
    # method = df.columns.get_level_values(0)[0]
    #  # get unit of measure from column index
    # unit = df.columns.get_level_values(1)[0].strip('[]').title()
    # # set graph visibility
    # visible = True if trace_count == 0 else False
    # # drop multi index columns
    # df.columns = df.columns.droplevel([0,1])
    # df = df.reset_index()
    # trace = go.Choropleth(
    #                     geojson=json.loads(regions_gdf.geometry.to_json()),
    #                     locationmode="geojson-id",
    #                     locations=df['index'],
    #                     z=df['Total'],
    #                     zauto=True,
    #                     # coloraxis=f'coloraxis{i+1}',
    #                     colorscale=color_scale,
    #                     colorbar={'title': f'{method}<br>{unit}',
    #                               'len':0.3},
    #                     customdata= df[['index']],
    #                     hovertemplate=  '<b>Region</b>: %{customdata[0]}<br>' +
    #                                     '<b>Regional CDR Potential</b>: %{z:,.0f} ' + unit + '<br>' +
    #                                     '%{text}' +
    #                                     '<extra></extra>',
    #                     text = df['Text'],
    #                     visible = visible
    # )
    # Add region names back into dataframe
    df['Region'] = df.index
    df['Count'] = 1 # range(len(df)) # random.sample(range(len(df)), len(df))
    print(df.columns)
    trace = go.Choropleth(
                        geojson=json.loads(regions_gdf.geometry.to_json()),
                        locationmode="geojson-id",
                        locations=[region],
                        # featureidkey='properties.GEO_ID',
                        z=[1],
                        zauto=True,
                        
                        #coloraxis='coloraxis',
                        colorscale=color_scale,
                        customdata=df.loc[region, ['Region', 'maxcol1', 'maxcol2']],
                        hovertemplate=  '<b>Region</b>: %{customdata[0]}<br>' +
                                        '<b>Top Two Methods: <b><br>' +
                                        '%{customdata[1][2]}<br>' +
                                        '%{customdata[2][2]}<br>' +
                                        '<extra></extra>')
    return trace

fig = go.Figure()

# make plots
# for i, df in enumerate(methods_dfs):
#     fig.add_trace(make_choro_trace(df, i))
#     # print(fig.data)
print(regions_top2_df.index)

for i, region in enumerate(regions_top2_df.index):
    # get color for region
    color = colors_set[i]
    # filter df for region
    # temp_df = pd.DataFrame(regions_top2_df.loc[region, :])

    fig.add_trace(make_choro_trace(regions_top2_df, region, [[0, 'green'], [1, 'green']]))
fig.update_geos(scope='usa')

# Colorscales: Blackbody,Bluered,Blues,Cividis,Earth,Electric,Greens,Greys,Hot,Jet,Picnic,Portland,Rainbow,RdBu,Reds,Viridis,YlGnBu,YlOrRd.
# create buttons to filter between wet and dry
# need list of dicts for buttons. Creates a button for each method setting that method's visibility to True
# buttons = [dict(method='update', label=label, args=[{'visible':[j == i for j in range(0,5)]}]) for i, label in enumerate(methods_units.get_level_values(0))]

# updatemenu = go.layout.Updatemenu(
#     type="buttons",
#     direction="right",
#     showactive=True,
#     x=0.8,
#     y=1.1,
#     buttons=buttons
# )

# fig.update_layout(
#     updatemenus=[updatemenu],
# )
fig.update_traces(showscale=False) #Removes color bar
fig.show()
fig.write_html('chapter_maps/regional_map.html')



