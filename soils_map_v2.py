from xml.etree.ElementPath import prepare_self
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
soils_path = 'data/Soils CDR'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data/label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})

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

# Soils data is seperated into ifferent files for each of the 3 practices
soils_cdr_path_dict = {'carbon_crop':'data/Soils CDR/EVcumulativeCDRbycounty_withcost.csv',
                       'perennial_borders':'data/Soils CDR/SupplyCurve_Conservation Buffer2025_MIROC_ES2LPerformance.csv',
                       'cover_crop':'data/Soils CDR/SupplyCurve_Cover Crop2025_MIROC_ES2LPerformance.csv'
                      }

summary_soils_path = 'data/Soils CDR/Soils summary data Nov.csv'
summary_df = pd.read_csv(summary_soils_path, dtype={'county_fips':str})
summary_df['county_fips'] = summary_df['county_fips'].apply(lambda x: x.zfill(5))

# merge with county state df
summary_df = summary_df.merge(county_fips_df, left_on='county_fips', right_on='FIPS')
# add this text so it matches geojson counties
summary_df['GEO_ID'] = '0500000US' + summary_df['FIPS']

# process data
for practice in ['Carboncrop', 'Covercrop', 'FieldBorder']:
    # Calculate CDR per land area per year
    summary_df['CDR_per_ha_per_year_' + practice] = summary_df['CDR_per_year_' + practice] / summary_df['TotalCountyAreaHa']
    # round price to the 10s place
    summary_df['Cost_USD_per_Mg_CDR_' + practice] = summary_df['Cost_USD_per_Mg_CDR_' + practice].round(-1)


cdr_per_year_col = 'CDR per Year'
cdr_per_area_col = 'CDR per Ha per Year'
cdr_cost_col = 'Tonnes CDR per USD'

summary_cols = {'CDR_per_year_Carboncrop': ('Carbon Crop', cdr_per_year_col),
                'CDR_per_ha_per_year_Carboncrop': ('Carbon Crop', cdr_per_area_col),
                'Cost_USD_per_Mg_CDR_Carboncrop': ('Carbon Crop', cdr_cost_col),
                'CDR_per_year_Covercrop': ('Cover Crop', cdr_per_year_col),
                'CDR_per_ha_per_year_Covercrop': ('Cover Crop', cdr_per_area_col),
                'Cost_USD_per_Mg_CDR_Covercrop': ('Cover Crop', cdr_cost_col),
                'CDR_per_year_FieldBorder': ('Perennial Borders', cdr_per_year_col),
                'CDR_per_ha_per_year_FieldBorder': ('Perennial Borders', cdr_per_area_col),
                'Cost_USD_per_Mg_CDR_FieldBorder': ('Perennial Borders', cdr_cost_col),
                'Combined_CDR_per_year': ('All Practices', cdr_per_year_col),
                'Combined_CDR_per_year_per_ha_cropland': ('All Practices', cdr_per_area_col)
                }

# protext county info in index
summary_df = summary_df.set_index(['GEO_ID', 'County, State'])
# keep only relevant columns
summary_df = summary_df.loc[:, summary_cols.keys()]
# convert columns to multiindex
summary_df.columns = pd.MultiIndex.from_tuples(summary_cols.values())
# convert to numeric
summary_df = summary_df.apply(pd.to_numeric, errors='coerce')

# get the top practice by cdr per ha per year
idx = pd.IndexSlice
summary_df[('All Practices', 'Top Practice')] = summary_df.loc[:, idx[['Carbon Crop', 'Cover Crop', 'Perennial Borders'], cdr_per_area_col]].idxmax(axis=1)
# drop any row that didn't have a top practice
summary_df = summary_df.dropna(subset=[('All Practices', 'Top Practice')])

# take only the first entry from the tuple returned in idx max
summary_df[('All Practices', 'Top Practice')] = summary_df[('All Practices', 'Top Practice')].apply(lambda x: x[0])
print(summary_df.loc[:,idx['All Practices',:]].head())

# Color Scheme for Soils Practices
color_dict = {'Carbon Crop': ['#FFFFFF', "#eecf43"], #sns.diverging_palette('#FFFFFF', "#eecf43", n=n_colors).as_hex(),
              'Perennial Borders': ['#FFFFFF', '#3182c1'], # sns.light_palette('#3182c1', n_colors).as_hex(), 
              'Cover Crop': ['#FFFFFF', '#59b375'], # sns.light_palette('#59b375', n_colors).as_hex()
            }

# geo json file
from urllib.request import urlopen
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

# make choropleth for soils map
fig = go.Figure(go.Choropleth())
fig.update_geos(scope='usa')

# Convert to million tons
#summary_df[('All Practices', 'CDR per Year')] = summary_df[('All Practices', 'CDR per Year')] /1000000

# convert per area to 100 Ha
summary_df[('All Practices', cdr_per_area_col)] = summary_df[('All Practices', cdr_per_area_col)] * 100
summary_df[('All Practices', cdr_per_area_col)] = summary_df[('All Practices', cdr_per_area_col)].round(2)

# Round all practicescdr per year for readability
summary_df[('All Practices', cdr_per_year_col)] = summary_df[('All Practices', cdr_per_year_col)].round(-2)

# create a trace for each practice
for practice in ['Carbon Crop', 'Perennial Borders', 'Cover Crop']:
    # filter for practice
    df = summary_df.loc[summary_df[('All Practices', 'Top Practice')] == practice]
    df = df.reset_index()
    df = df.fillna(0)
    df = df[df[('All Practices', cdr_per_year_col)] > 0]
    print(f'95% cutoff Value {practice}:', df[('All Practices', cdr_per_area_col)].quantile(.95))
    # create map
    fig.add_trace(trace=go.Choropleth(
        geojson=counties,
        locationmode="geojson-id",
        locations=df['GEO_ID'],
        featureidkey='properties.GEO_ID',
        # z=np.log10(df[('Cumulative', cdr_per_area_col)]),
        z=df[(practice, cdr_per_area_col)] * 100,
        zmax=df[(practice, cdr_per_area_col)].quantile(.95) * 100,
        zmin=df[(practice, cdr_per_area_col)].min() * 100,
        colorscale=color_dict.get(practice, 'reds'),
        customdata=df[[('All Practices', 'Top Practice'), ('County, State', ''), 
                       ('All Practices', cdr_per_year_col), ('All Practices', cdr_per_area_col), (practice, cdr_cost_col)]],
        hovertemplate='<b>Top Practice per Area</b>: %{customdata[0]}<br>' +
                        '<b>County</b>: %{customdata[1]}<br>' +
                        '<b>All Practices CDR Potential</b>: %{customdata[2]:,.0f} Tonnes CO<sub>2</sub> per Year<br>' +
                        '<b>All Practices CDR per Area</b>: %{customdata[3]:,.2f} Tonnes CO<sub>2</sub> per 100 Hectares per Year<br>' +
                        f'<b>{practice} Cost</b>: ' + '$%{customdata[4]:,.0f} per Tonne CO<sub>2</sub><br>' +
                        '<extra></extra>'))
    
    # Get rid of color bar. All color bars overlap right now, so it looks neater without them
    # fig.update_traces(showscale=False)
    
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

fontsize=10
# assign each trace to new color axis
for i, trace in enumerate(fig.data, 1):
    trace.update(coloraxis=f"coloraxis{i}")

cbar_title_units = 'CO<sub>2</sub> Removal Potential Over Total County Area<br>Tonnes CO<sub>2</sub> per 100 Hectares per Year'

# Add color scales
fig.update_layout(
    coloraxis1={"colorbar": {"x": -0.2, "len": 0.5, "y": 0.8}},
    coloraxis2={
        "colorbar": {
            "x": 0.2,
            "len": 0.2,
            "y": -0.3,
            'title':'Carbon Cropping<br>' + cbar_title_units,
            'orientation':'h',
            'titlefont':{'size':fontsize},
            'tickfont':{'size':fontsize}},
        "colorscale":color_dict.get('Carbon Crop'),
        'cmax':summary_df[('Carbon Crop', cdr_per_area_col)].quantile(0.98) * 100,
        'cmin': 0
    },
    coloraxis3={
        "colorbar": {"x": 0.5, 
                     "len": 0.2, 
                     "y": -.3, 
                     'title':'Perennial Borders<br>' + cbar_title_units,
                     'orientation':'h',
                     'titlefont':{'size':fontsize},
                     'tickfont':{'size':fontsize}},
        "colorscale":color_dict.get('Perennial Borders', 'Viridis'),
        'cmax': summary_df[('Perennial Borders', cdr_per_area_col)].quantile(0.98) * 100,
        'cmin': 0
    },
    coloraxis4={
        "colorbar": {"x": 0.8, 
                     "len": 0.2, 
                     "y": -.3,
                     'title':'Cover Crop<br>' + cbar_title_units,
                     'orientation':'h',
                     'titlefont':{'size':fontsize},
                     'tickfont':{'size':fontsize}},
        "colorscale": color_dict.get('Cover Crop', 'Viridis'),
        'cmax': summary_df[('Cover Crop', cdr_per_area_col)].quantile(0.98) * 100,
        'cmin': 0
            })

fig.update_coloraxes(colorbar_title_side='top')
fig.write_html('chapter_maps/soils_map.html')

for i in range(len(fig.data)):
    fig.update_layout({f'coloraxis{i+1}':{'showscale':False}})

fig.show()
fig.write_html('chapter_maps/soils_map_nocbar.html')



