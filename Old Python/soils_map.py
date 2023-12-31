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
soils_path = 'data\Soils CDR'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data\label_geography.csv', dtype={'geography':'str'})
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
soils_cdr_path_dict = {'carbon_crop':'data\Soils CDR\EVcumulativeCDRbycounty_withcost.csv',
                       'perennial_borders':'data\Soils CDR\SupplyCurve_Conservation Buffer2025_MIROC_ES2LPerformance.csv',
                       'cover_crop':'data\Soils CDR\SupplyCurve_Cover Crop2025_MIROC_ES2LPerformance.csv'
                      }

summary_soils_path = 'data\Soils CDR\Soils summary data Nov.csv'
summary_df = pd.read_csv(summary_soils_path, dtype=('county_fips':str))

# Calculate CDR per land area per year
for practice in ['Carboncrop', 'Covercrop', 'FieldBorder']:
    summary_df['CDR_per_ha_per_year_' + practice] = ['CDR_per_year_' + practice] / summary_df['TotalCountyAreaHa']

summary_cols = {'CDR_per_year_Carboncrop': ('Carbon Crop', 'CDR per Year'),
                'CDR_per_ha_per_year_Carboncrop': ('Carbon Crop', 'CDR per Ha per Year'),
                'Cost_USD_per_Mg_CDR_Carboncrop': ('Carbon Crop', 'Tonnes CDR per USD'),
                'CDR_per_year_Covercrop': ('Cover Crop', 'CDR per Year'),
                'CDR_per_ha_per_year_Covercrop': ('Cover Crop', 'CDR per Ha per Year'),
                'Cost_USD_per_Mg_CDR_Covercrop': ('Cover Crop', 'Tonnes CDR per USD'),
                'CDR_per_year_FieldBorder': ('Perennial Borders', 'CDR per Year'),
                'CDR_per_ha_per_year_Carboncrop': ('Carbon Crop', 'CDR per Ha per Year'),
                'Cost_USD_per_Mg_CDR_FieldBorder': ('Perennial Borders', 'Tonnes CDR per USD'),
                'Combined_CDR_per_year': ('All Practices', 'CDR per Year'),
                'Combined_CDR_per_year_per_ha_cropland': ('All Practices', 'CDR per Ha per Year')

                }

# variables for calculated column names
cum_cdr_col = 'Cumulative Tonnes CDR'
cdr_per_area_col = 'Cumulative Tonnes CDR per Hectare'
cost_cdr_col = 'Tonnes CDR per USD'

def proccess_soils_cdr(key, path, cum_cdr_col, cdr_per_area_col, cost_cdr_col, min_negemissions=100, min_area=15, price_per_tonne=40):
    """
    Reads soils cdr data and standardizes the format.

    Some counties, like Ontario, NY, have very small cropland areas and cause erroneous results on the pre area metrics. That's why we filter for minimum area and neg emissions
    
    These calculations are based on $40 CO2 price
    """
    df = pd.read_csv(path)
    
    if key == 'carbon_crop':
        # fix fips
        df['County_FIPS'] = df['County_FIPS'].apply(lambda x: str(x).zfill(5))

        # filter for correct CO2 price
        df = df.loc[(df['bc']=='40 67')&(df['sgarea']>min_area)&(df['Negative_emissions_cumulative']>25*min_negemissions)]
        df[cum_cdr_col] = df['Negative_emissions_cumulative']
        df[cdr_per_area_col] = df['Negative_emissions_cumulative']/df['sgarea']
        df[cost_cdr_col] = df['Negative_emissions_cumulative']/(price_per_tonne*df['climate_benefit_cumulative'])
        df['Practice'] = 'Carbon Cropping'
        
        # Keep only relevant data from oriinal spreadsheet
        save_cols=['Practice', 'County_FIPS', cum_cdr_col, cdr_per_area_col, cost_cdr_col]
        df = df.loc[:,save_cols]
        df = df.rename(columns={'County_FIPS':'GEOID'})

    else:
        # There are multiple county fips columsn in this data set! Make sure to use the all lowercase one
        df['county_fips'] = df['county_fips'].apply(lambda x: str(x).zfill(5))
        # get rows where co2 price is 40 & where cropland area > 0
        df = df.loc[(df['CO2price']==price_per_tonne)&(df["converted.ha_combined25_sgadjusted"]>0)&(df["converted.ha_combined25_sgadjusted"]>min_area)&(df['Negative_emissions_MgCO2_per_year_combined25_sgadjusted']>min_negemissions),:]
        # change conservation buffer to perennial borders
        if key=='perennial_borders':
            df['Practice'] = 'Perennial Borders'
        # the data are in CO2 removed per year. Need to multiply by 25 to get Cumulative CDR
        df.plot(kind='scatter', y='Negative_emissions_MgCO2_per_year_combined25_sgadjusted', x="converted.ha_combined25_sgadjusted", alpha=0.5)
        df[cum_cdr_col] = 25*df['Negative_emissions_MgCO2_per_year_combined25_sgadjusted']
        df[cdr_per_area_col] = (25*df['Negative_emissions_MgCO2_per_year_combined25_sgadjusted'])/df["converted.ha_combined25_sgadjusted"]
        df[cost_cdr_col] = df['Negative_emissions_MgCO2_per_year_combined25_sgadjusted']/(price_per_tonne*df['Total_climate_benefit_MgCO2e_per_year_combined25_sgadjusted'])
        # save extra columns if save_csvs is true
        save_cols=['Practice', 'county_fips',cum_cdr_col, cdr_per_area_col, cost_cdr_col]
        df = df.loc[:,save_cols]
        df = df.rename(columns={'county_fips':'GEOID'})     
        
    df = df.dropna()
    # sort negative emissions by ascending and drop the first duplicate. This reports a more conservative number in the case of duplicates
    df = df.sort_values(by=['GEOID', cum_cdr_col, cdr_per_area_col], ascending=[True, True, True])
    df = df.drop_duplicates(subset=['GEOID', 'Practice'])
    # Get county state name
    df = df.merge(county_fips_df, left_on='GEOID', right_on='FIPS')
    # need GEO_ID to match the fips format in the shapefile
    df['GEO_ID'] = '0500000US' + df['GEOID']
    return df

# create one df of all soils practices
soils_cdr_dfs = [proccess_soils_cdr(key, path, cum_cdr_col, cdr_per_area_col, cost_cdr_col, min_negemissions=100, min_area=15) for key, path in soils_cdr_path_dict.items()]
merged_soils_df = pd.concat(soils_cdr_dfs, axis=0)
merged_soils_df = merged_soils_df.drop(columns=['geo_level', 'FIPS'])
merge_soils_df = merged_soils_df.fillna(0)
practices = merged_soils_df['Practice'].unique()

# dict mapping color scale to practice
n_colors = 6
color_dict = {'Carbon Cropping': ['#FFFFFF', "#eecf43"], #sns.diverging_palette('#FFFFFF', "#eecf43", n=n_colors).as_hex(),
              'Perennial Borders': ['#FFFFFF', '#3182c1'], # sns.light_palette('#3182c1', n_colors).as_hex(), 
              'Cover Crop': ['#FFFFFF', '#59b375'], # sns.light_palette('#59b375', n_colors).as_hex()
            }
# create multilevel column index for each practice
pivot_df = merged_soils_df.pivot(index=['GEOID', 'GEO_ID', 'County, State'], columns='Practice').swaplevel(axis=1)
idx = pd.IndexSlice
# calculate cumulative values for each cdr metric
for metric in [cum_cdr_col, cdr_per_area_col]:
    pivot_df[('Cumulative', metric)] = pivot_df.loc[:, idx[practices, metric]].sum(axis=1)
# get the max cdr method
pivot_df[('Cumulative', 'Max Practice')] = pivot_df.loc[:, idx[practices, cdr_per_area_col]].idxmax(axis=1)
pivot_df[('Cumulative', 'Max Practice')] = pivot_df[('Cumulative', 'Max Practice')].apply(lambda x: x[0])

# geo json file
from urllib.request import urlopen
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

# make choropleth for soils map
fig = go.Figure(go.Choropleth())
fig.update_geos(scope='usa')

# create a trace for each practice
for practice in practices:
    # filter for practice
    df = pivot_df.loc[pivot_df[('Cumulative', 'Max Practice')] == practice]
    df = df.reset_index()
    df = df.fillna('No Data')
    # print(df.columns)
    # print(df.head())
    print(f'95% cutoff Value {practice}:', df[('Cumulative', cdr_per_area_col)].quantile(.95))
    # create map
    fig.add_trace(trace=go.Choropleth(
        geojson=counties,
        locationmode="geojson-id",
        locations=df['GEO_ID'],
        featureidkey='properties.GEO_ID',
        # z=np.log10(df[('Cumulative', cdr_per_area_col)]),
        z=df[(practice, cdr_per_area_col)],
        zmax=df[(practice, cdr_per_area_col)].quantile(.95),
        zmin=df[(practice, cdr_per_area_col)].min(),
        colorscale=color_dict.get(practice, 'reds'),
        customdata=df[[('Cumulative', 'Max Practice'), ('County, State', ''), 
                       ('Cumulative', cum_cdr_col), ('Cumulative', cdr_per_area_col), (practice, cost_cdr_col)]],
        hovertemplate='<b>Top Practice per Area</b>: %{customdata[0]}<br>' +
                        '<b>County</b>: %{customdata[1]}<br>' +
                        '<b>All Practices CDR Potential by 2050</b>: %{customdata[2]:,.0f} Tonnes CO<sub>2</sub><br>' +
                        '<b>All Practices CDR per Area</b>: %{customdata[3]:,.0f} Tonnes CO<sub>2</sub> per Hectare<br>' +
                        f'<b>{practice} CDR per Dollar</b>: ' + '%{customdata[4]:,.2f} Tonnes CO<sub>2</sub> per USD<br>' +
                        '<extra></extra>'))
    
    # Get rid of color bar. All color bars overlap right now, so it looks neater without them
    # fig.update_traces(showscale=False)
    
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

fontsize=10
# assign each trace to new color axis
for i, trace in enumerate(fig.data, 1):
    trace.update(coloraxis=f"coloraxis{i}")

# Add color scales
fig.update_layout(
    coloraxis1={"colorbar": {"x": -0.2, "len": 0.5, "y": 0.8}},
    coloraxis2={
        "colorbar": {
            "x": 0.9,
            "len": 0.2,
            "y": 0.8,
            'title':'Carbon Cropping<br>Tonnes CO<sub>2</sub> per Hectare',
            'orientation':'h',
            'titlefont':{'size':fontsize},
            'tickfont':{'size':fontsize}},
        "colorscale":color_dict.get('Carbon Cropping'),
        'cmax':pivot_df[('Carbon Cropping', cdr_per_area_col)].quantile(0.98),
        'cmin':0
    },
    coloraxis3={
        "colorbar": {"x": 0.9, 
                     "len": 0.2, 
                     "y": 0.6, 
                     'title':'Perennial Borders<br>Tonnes CO<sub>2</sub> per Hectare',
                     'orientation':'h',
                     'titlefont':{'size':fontsize},
                     'tickfont':{'size':fontsize}},
        "colorscale":color_dict.get('Perennial Borders', 'Viridis'),
        'cmax':pivot_df[('Perennial Borders', cdr_per_area_col)].quantile(0.98),
        'cmin':0
    },
    coloraxis4={
        "colorbar": {"x": 0.9, 
                     "len": 0.2, 
                     "y": 0.4,
                     'title':'Cover Crop<br>Tonnes CO<sub>2</sub> per Hectare',
                     'orientation':'h',
                     'titlefont':{'size':fontsize},
                     'tickfont':{'size':fontsize}},
        "colorscale": color_dict.get('Cover Crop', 'Viridis'),
        'cmax':pivot_df[('Cover Crop', cdr_per_area_col)].quantile(0.98),
        'cmin':0
            })

fig.show()
fig.write_html('chapter_maps/soils_map.html')



