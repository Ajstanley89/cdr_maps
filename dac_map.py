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
dac_path = 'data/DAC CDR'

# data from census linking county name and fips
county_fips_df = pd.read_csv('data/label_geography.csv', dtype={'geography':'str'})
county_fips_df = county_fips_df[county_fips_df['geo_level']=='C']
county_fips_df = county_fips_df.rename(columns={'label':'County, State', 'geography':'FIPS'})

# load DAC data
sorbent_df = pd.read_csv(dac_path + '/Sorbent_HP_2050_Cty_wtavg_11_cutoff-100ktpa.csv', dtype={'county':str})
solvent_df = pd.read_csv(dac_path + '/Solvent_2050_Cty_wtavg_11.csv', dtype={'county':str})

# rename columns to something pretty
sorbent_df = sorbent_df.rename(columns={'county_DACcap_tpa':'Sorbent CDR Capacity',
                                        'county_DACcost_wtavg':'Sorbent Cost'})
solvent_df = solvent_df.rename(columns={'cty_region_DACcap_tpa':'Solvent Region CDR Capacity',
                                        'county_DACcost_wtavg':'Solvent Weighted Average Cost'})
# round numbers
sorbent_df['Sorbent CDR Capacity'] = sorbent_df['Sorbent CDR Capacity'].round(-3)
solvent_df['Solvent Region CDR Capacity'] = solvent_df['Solvent Region CDR Capacity'].round(-3)
sorbent_df['Sorbent Cost'] = sorbent_df['Sorbent Cost'].round(-1)

# merge everthing together
dac_df = sorbent_df.merge(solvent_df, on='county')
dac_df = dac_df.merge(county_fips_df, left_on='county', right_on='FIPS')
dac_df['GEO_ID'] = '0500000US' + dac_df['county']

# geo json file
from urllib.request import urlopen
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

# make choropleth for dac. Use colors for sorbent only, but report solvent as well on hover text
fig = go.Figure(go.Choropleth())
fig.update_geos(scope='usa')

# Convert to million tons
dac_df['Sorbent CDR Capacity'] = dac_df['Sorbent CDR Capacity']/1000000

# geostorage map only needs one trace
fig.add_trace(trace=go.Choropleth(
    geojson=counties,
    locationmode="geojson-id",
    locations=dac_df['GEO_ID'],
    featureidkey='properties.GEO_ID',
    z=dac_df['Sorbent CDR Capacity'],
    zmax=dac_df['Sorbent CDR Capacity'].quantile(.95),
    zmin=dac_df['Sorbent CDR Capacity'].quantile(.05),
    colorscale='greens',
    customdata=dac_df[['County, State', 'Sorbent CDR Capacity', 'Sorbent Cost', 'Solvent Region CDR Capacity', 'Solvent Weighted Average Cost']],
    hovertemplate='<b>County</b>: %{customdata[0]}<br>' +
                    '<b>Adsorbent DACS CDR Potential </b>: %{customdata[1]:,.0f} Million Tonnes CO<sub>2</sub> Per Year<br>' +
                    '<b>Adsorbent CDR Cost</b>: %{customdata[2]:,.0f} USD per Tonne CO<sub>2</sub><br>' +
                    # '<b>Regional Solvent CDR Potential by 2050</b>: %{customdata[3]:,.0f} Tonnes CO<sub>2</sub><br>' +
                    # '<b>Regional Solvent CDR Cost</b>: %{customdata[4]:,.2f} USD per Tonne CO<sub>2</sub><br>' +
                    '<extra></extra>'))

# Get rid of color bar. All color bars overlap right now, so it looks neater without them
# fig.update_traces(showscale=False)

for i, trace in enumerate(fig.data, 1):
    trace.update(coloraxis=f"coloraxis{i}")
    
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0},
                  coloraxis2={"colorbar": {"x": 0.50, 
                                           "len": 0.75, 
                                           "y": -0.3, 
                                           'title':'Potential Adsorbent DACS Capacity<br>Tonnes CO<sub>2</sub> Removed Per Year',
                                           'orientation':'h',
                                           'titlefont':{'size':10},
                                           'tickfont':{'size':10}
                                           },
                                'colorscale':'greens',
                                'cmax':dac_df['Sorbent CDR Capacity'].quantile(.98),
                                'cmin':0})

fig.update_coloraxes(colorbar_title_side='top')
fig.write_html('chapter_maps/dac_map.html')
# save version with no cbar
for i in range(len(fig.data)):
    fig.update_layout({f'coloraxis{i+1}':{'showscale':False}})

fig.show()
fig.write_html('chapter_maps/dac_map_nocbar.html')



