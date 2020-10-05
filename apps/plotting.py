# Copyright 2020 AstroLab Software
# Author: Julien Peloton
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pandas as pd

import java

import plotly.graph_objects as go

from apps.utils import convert_jd, readstamp, _data_stretch
from apps.utils import extract_row

from app import client

layout_lightcurve = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(font=dict(size=10), orientation="h"),
    xaxis={
        'title': 'Observation date'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude'
    }
)

def extract_lightcurve(data: java.util.TreeMap) -> pd.DataFrame:
    """
    """
    pdfs = pd.DataFrame()
    values = ['i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid']
    for rowkey in data:
        if rowkey == '':
            continue
        properties = extract_row(rowkey, data)
        pdf = pd.DataFrame.from_dict(
            properties, orient='index', columns=[rowkey]).T[values]
        pdfs = pd.concat((pdfs, pdf))
    return pdfs

def draw_lightcurve(data: java.util.TreeMap) -> dict:
    """ Draw object lightcurve with errorbars

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query

    Returns
    ----------
    figure: dict
    """
    pdf = extract_lightcurve(data)

    jd = pdf['i:jd']
    jd = jd.apply(lambda x: convert_jd(float(x), to='iso'))
    figure = {
        'data': [
            {
                'x': jd[pdf['i:fid'] == '1'],
                'y': pdf['i:magpsf'][pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'][pdf['i:fid'] == '1'],
                    'visible': True,
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'text': jd[pdf['i:fid'] == '1'],
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            },
            {
                'x': jd[pdf['i:fid'] == '2'],
                'y': pdf['i:magpsf'][pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'][pdf['i:fid'] == '2'],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'text': jd[pdf['i:fid'] == '2'],
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
        ],
        "layout": layout_lightcurve
    }
    return figure

def extract_latest_cutouts(data: java.util.TreeMap):
    """ Extract cutout data from the alert

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query

    Returns
    ----------
    science: np.array
        2D array containing science data
    template: np.array
        2D array containing template data
    difference: np.array
        2D array containing difference data
    """
    pdfs = pd.DataFrame()
    values = [
        'i:jd',
        'b:cutoutScience_stampData',
        'b:cutoutTemplate_stampData',
        'b:cutoutDifference_stampData'
    ]
    for rowkey in data:
        if rowkey == '':
            continue
        properties = extract_row(rowkey, data)
        pdf = pd.DataFrame.from_dict(
            properties, orient='index', columns=[rowkey]).T[values]
        pdfs = pd.concat((pdfs, pdf))
    pdfs.sort_values('i:jd', ascending=False)
    diff = readstamp(
        client.repository().get(pdfs['b:cutoutDifference_stampData'].values[0]))
    science = readstamp(
        client.repository().get(pdfs['b:cutoutScience_stampData'].values[0]))
    template = readstamp(
        client.repository().get(pdfs['b:cutoutTemplate_stampData'].values[0]))
    return science, template, diff

def draw_cutout(data, title):
    """ Display alert data and stamps based on its ID.

    By default, the data curve is the light curve (magpsd vs jd).

    Callbacks
    ----------
    Input: alert_id coming from the `alerts-dropdown` menu
    Input: field_name coming from the `field-dropdown` menu
    Output: Graph to display the historical light curve data of the alert.
    Output: stamps (Science, Template, Difference)

    Parameters
    ----------
    alert_id: str
        ID of the alerts (must be unique and saved on disk).
    field_name: str
        Name of the alert field to plot (default is None).

    Returns
    ----------
    html.div: Graph data and layout based on incoming alert data.
    """
    # Update graph data for stamps
    data = _data_stretch(data, stretch='linear')
    data = data[::-1]
    # data = convolve(data)

    fig = go.Figure(
        data=go.Heatmap(
            z=data, showscale=False, colorscale='greys'
        )
    )

    axis_template = dict(
        autorange=True,
        showgrid=False, zeroline=False,
        linecolor='black', showticklabels=False,
        ticks='')

    fig.update_layout(
        title=title,
        margin=dict(t=0, r=0, b=0, l=0),
        xaxis=axis_template,
        yaxis=axis_template,
        showlegend=True,
        width=150, height=150,
        autosize=False)

    return fig