from requests import get
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import os

# folder holding all forestry cdr data
forestry_path = 'data\Foresty CDR'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data\label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})
print(county_fips_df.head())

def process_forestry_cdr(df):
    """
    Standardizes fips formatting for cdr dfs
    
    First Column must be FIPS column and last column must be CDR column
    """
    df = df.rename(columns={df.columns[0]:'FIPS',
                           df.columns[-1]:'Total Tonnes CDR'})
    df['FIPS'] = df['FIPS'].apply(lambda x: str(x).zfill(5))
    # need to add '0500000US' to each GEOID so it matches th geo json file
    df['GEO_ID'] = '0500000US' + df['FIPS']
    df = df.merge(county_fips_df, on='FIPS')
    return df[df['Total Tonnes CDR']>0]

# forestry data is in 3 different spreadsheets
ne_cdr_df = pd.read_csv(forestry_path + "\\" + 'NE_Forest Area.csv', dtype={'FID':str})
se_cdr_df = pd.read_excel(forestry_path + '\\' + 'Total carbon stock change by county restoration 2050 high density.xlsx', dtype={'FIPS_County':str})
w_cdr_df = pd.read_csv(forestry_path + '\\' + 'western_county_potentials_with_names.csv', dtype={'FIPS_County':str})

forest_names = ['Northeastern Forests', 'Southeastern Forests', 'Western Forests']
forestry_cdr_dfs = {forest:process_forestry_cdr(df) for forest, df in zip(forest_names, [ne_cdr_df, se_cdr_df, w_cdr_df])}
forest_color_scales = {forest:color for forest, color in zip(forest_names, ['greens', 'blues', 'reds'])}

# geo json file
from urllib.request import urlopen
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)


# make choropleth for forestry map
fig = go.Figure(go.Choropleth())
fig.update_geos(scope='usa')

# create a trace for each forest's data
for key, df in forestry_cdr_dfs.items():
    print(df.head())
    fig.add_trace(trace=go.Choropleth(
        geojson=counties,
        locationmode="geojson-id",
        locations=df['GEO_ID'],
        featureidkey='properties.GEO_ID',
        z=df['Total Tonnes CDR'].round(-3),
        zmin=df['Total Tonnes CDR'].min(),
        zmax=df['Total Tonnes CDR'].max(),
        colorscale=forest_color_scales.get(key, 'viridis'),
        colorbar_title=key,
        name=key,
        customdata=df[['County, State', 'Total Tonnes CDR']],
        hovertemplate='<b>County</b>: %{customdata[0]}<br>' +
                        '<b>Cummulative CDR</b>: %{z:,.0f} Tonnes CO2<br>' +
                        '<extra></extra>'))
    
    # Get rid of color bar. All color bars overlap right now, so it looks neater without them
    fig.update_traces(showscale=False)
    
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

fig.show()
fig.write_html('chapter_maps/forestry_map.html')



