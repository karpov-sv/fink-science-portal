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
import numpy as np
from gatspy import periodic

import java
import copy
from astropy.time import Time

from dash.dependencies import Input, Output
import plotly.graph_objects as go

from apps.utils import convert_jd, readstamp, _data_stretch, convolve
from apps.utils import apparent_flux, dc_mag
from apps.mulens_helper import fit_ml_de_simple, mulens_simple

from app import client, app

colors_ = [
    '#1f77b4',  # muted blue
    '#ff7f0e',  # safety orange
    '#2ca02c',  # cooked asparagus green
    '#d62728',  # brick red
    '#9467bd',  # muted purple
    '#8c564b',  # chestnut brown
    '#e377c2',  # raspberry yogurt pink
    '#7f7f7f',  # middle gray
    '#bcbd22',  # curry yellow-green
    '#17becf'   # blue-teal
]

layout_lightcurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        bgcolor='rgba(0,0,0,0)'
    ),
    xaxis={
        'title': 'Observation date',
        'automargin': True
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude',
        'automargin': True
    }
)

layout_phase = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=40, t=25),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        yanchor="bottom",
        y=0.02,
        xanchor="right",
        x=1,
        bgcolor='rgba(0,0,0,0)'
    ),
    xaxis={
        'title': 'Phase'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Apparent DC Magnitude'
    },
    title={
        "text": "Phased data",
        "y": 1.01,
        "yanchor": "bottom"
    }
)

layout_mulens = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=40, t=25),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor='rgba(0,0,0,0)'
    ),
    xaxis={
        'title': 'Observation date'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'DC magnitude'
    },
    title={
        "text": "Fit",
        "y": 1.01,
        "yanchor": "bottom"
    }
)

layout_scores = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(font=dict(size=10), orientation="h"),
    xaxis={
        'title': 'Observation date'
    },
    yaxis={
        'title': 'Score',
        'range': [0, 1]
    }
)

def extract_scores(data: java.util.TreeMap) -> pd.DataFrame:
    """ Extract SN scores from the data
    """
    values = ['i:jd', 'd:snn_snia_vs_nonia', 'd:snn_sn_vs_all', 'd:rfscore']
    pdfs = pd.DataFrame.from_dict(data, orient='index')
    if pdfs.empty:
        return pdfs
    return pdfs[values]

@app.callback(
    [
        Output('lightcurve_cutouts', 'figure'),
        Output('lightcurve_scores', 'figure')
    ],
    [
        Input('switch-mag-flux', 'value'),
        Input('url', 'pathname'),
        Input('object-data', 'children')
    ])
def draw_lightcurve(switch: int, pathname: str, object_data) -> dict:
    """ Draw object lightcurve with errorbars

    Parameters
    ----------
    switch: int
        Choose:
          - 0 to display difference magnitude
          - 1 to display dc magnitude
          - 2 to display flux
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    pdf_ = pd.read_json(object_data)
    cols = [
        'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
        'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos'
    ]
    pdf = pdf_.loc[:, cols]

    # type conversion
    jd = pdf['i:jd']
    jd = jd.apply(lambda x: convert_jd(float(x), to='iso'))

    pdf['i:fid'] = pdf['i:fid'].astype(str)

    # shortcuts
    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']
    if switch == 0:
        layout_lightcurve['yaxis']['title'] = 'Difference magnitude'
        layout_lightcurve['yaxis']['autorange'] = 'reversed'
    elif switch == 1:
        # inplace replacement
        mag, err = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:fid'].astype(int).values,
                    mag.astype(float).values,
                    err.astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:magzpsci'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )
        layout_lightcurve['yaxis']['title'] = 'Apparent DC magnitude'
        layout_lightcurve['yaxis']['autorange'] = 'reversed'
    elif switch == 2:
        # inplace replacement
        mag, err = np.transpose(
            [
                apparent_flux(*args) for args in zip(
                    pdf['i:fid'].astype(int).values,
                    mag.astype(float).values,
                    err.astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:magzpsci'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )
        layout_lightcurve['yaxis']['title'] = 'Apparent DC flux'
        layout_lightcurve['yaxis']['autorange'] = True

    figure = {
        'data': [
            {
                'x': jd[pdf['i:fid'] == '1'],
                'y': mag[pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == '1'],
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
                'y': mag[pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == '2'],
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
    return figure, figure

def draw_scores(data: java.util.TreeMap) -> dict:
    """ Draw scores from SNN module

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query

    Returns
    ----------
    figure: dict

    TODO: memoise me
    """
    pdf = extract_scores(data)

    jd = pdf['i:jd']
    jd = jd.apply(lambda x: convert_jd(float(x), to='iso'))
    figure = {
        'data': [
            {
                'x': jd,
                'y': [0.5] * len(jd),
                'mode': 'lines',
                'showlegend': False,
                'line': {
                    'color': 'black',
                    'width': 2.5,
                    'dash': 'dash'
                }
            },
            {
                'x': jd,
                'y': pdf['d:snn_snia_vs_nonia'],
                'mode': 'markers',
                'name': 'SN Ia score',
                'text': jd,
                'marker': {
                    'size': 10,
                    'color': '#2ca02c',
                    'symbol': 'circle'}
            },
            {
                'x': jd,
                'y': pdf['d:snn_sn_vs_all'],
                'mode': 'markers',
                'name': 'SNe score',
                'text': jd,
                'marker': {
                    'size': 10,
                    'color': '#d62728',
                    'symbol': 'square'}
            },
            {
                'x': jd,
                'y': pdf['d:rfscore'],
                'mode': 'markers',
                'name': 'Random Forest',
                'text': jd,
                'marker': {
                    'size': 10,
                    'color': '#9467bd',
                    'symbol': 'diamond'}
            }
        ],
        "layout": layout_scores
    }
    return figure

def extract_cutout(object_data, time0, kind):
    """ Extract cutout data from the alert

    Parameters
    ----------
    object_data: json
        Jsonified pandas DataFrame
    time0: str
        ISO time of the cutout to extract
    kind: str
        science, template, or difference

    Returns
    ----------
    data: np.array
        2D array containing cutout data
    """
    values = [
        'i:jd',
        'i:fid',
        'b:cutout{}_stampData'.format(kind.capitalize()),
    ]
    pdf_ = pd.read_json(object_data)
    pdfs = pdf_.loc[:, values]
    pdfs = pdfs.sort_values('i:jd', ascending=False)

    if time0 is None:
        position = 0
    else:
        # Round to avoid numerical precision issues
        jds = pdfs['i:jd'].apply(lambda x: np.round(x, 2)).values
        jd0 = np.round(Time(time0, format='iso').jd, 2)
        position = np.where(jds == jd0)[0][0]

    # Grab the cutout data
    cutout = readstamp(
        client.repository().get(
            pdfs['b:cutout{}_stampData'.format(kind.capitalize())].values[position]
        )
    )
    return cutout


@app.callback(
    Output("science-stamps", "figure"),
    [
        Input('lightcurve_cutouts', 'clickData'),
        Input('object-data', 'children'),
    ])
def draw_cutouts_science(clickData, object_data):
    """ Draw science cutout data based on lightcurve data
    """
    if clickData is not None:
        # Draw the cutout associated to the clicked data points
        jd0 = clickData['points'][0]['x']
    else:
        # draw the cutout of the last alert
        jd0 = None
    data = extract_cutout(object_data, jd0, kind='science')
    return draw_cutout(data, 'science')

@app.callback(
    Output("template-stamps", "figure"),
    [
        Input('lightcurve_cutouts', 'clickData'),
        Input('object-data', 'children'),
    ])
def draw_cutouts_template(clickData, object_data):
    """ Draw template cutout data based on lightcurve data
    """
    if clickData is not None:
        jd0 = clickData['points'][0]['x']
    else:
        jd0 = None
    data = extract_cutout(object_data, jd0, kind='template')
    return draw_cutout(data, 'template')

@app.callback(
    Output("difference-stamps", "figure"),
    [
        Input('lightcurve_cutouts', 'clickData'),
        Input('object-data', 'children'),
    ])
def draw_cutouts_difference(clickData, object_data):
    """ Draw difference cutout data based on lightcurve data
    """
    if clickData is not None:
        jd0 = clickData['points'][0]['x']
    else:
        jd0 = None
    data = extract_cutout(object_data, jd0, kind='difference')
    return draw_cutout(data, 'difference')

def draw_cutout(data, title):
    """ Draw a cutout data
    """
    # Update graph data for stamps
    size = len(data)
    data = np.nan_to_num(data)
    vmax = data[int(size / 2), int(size / 2)]
    vmin = np.min(data) + 0.2 * np.median(np.abs(data - np.median(data)))
    data = _data_stretch(data, vmin=vmin, vmax=vmax, stretch='asinh')
    data = data[::-1]
    data = convolve(data, smooth=1, kernel='gauss')

    fig = go.Figure(
        data=go.Heatmap(
            z=data, showscale=False, colorscale='Greys_r'
        )
    )
    # Greys_r

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

@app.callback(
    Output('variable_plot', 'figure'),
    [
        Input('nterms_base', 'value'),
        Input('nterms_band', 'value'),
        Input('manual_period', 'value'),
        Input('submit_variable', 'n_clicks'),
        Input('object-data', 'children')
    ])
def plot_variable_star(nterms_base, nterms_band, manual_period, n_clicks, object_data):
    """ Fit for the period of a star using gatspy

    See https://zenodo.org/record/47887
    See https://ui.adsabs.harvard.edu/abs/2015ApJ...812...18V/abstract

    TODO: clean me
    """
    if type(nterms_base) not in [int]:
        return {'data': [], "layout": layout_phase}
    if type(nterms_band) not in [int]:
        return {'data': [], "layout": layout_phase}
    if manual_period is not None and type(manual_period) not in [int, float]:
        return {'data': [], "layout": layout_phase}

    if n_clicks is not None:
        pdf_ = pd.read_json(object_data)
        cols = [
            'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
            'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos', 'i:objectId'
        ]
        pdf = pdf_.loc[:, cols]
        pdf['i:fid'] = pdf['i:fid'].astype(str)
        pdf = pdf.sort_values('i:jd', ascending=False)

        mag_dc, err_dc = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:fid'].astype(int).values,
                    pdf['i:magpsf'].astype(float).values,
                    pdf['i:sigmapsf'].astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:magzpsci'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )

        jd = pdf['i:jd']
        fit_period = False if manual_period is not None else True
        model = periodic.LombScargleMultiband(
            Nterms_base=int(nterms_base),
            Nterms_band=int(nterms_band),
            fit_period=fit_period
        )

        # Not sure about that...
        model.optimizer.period_range = (0.1, 1.2)
        model.optimizer.quiet = True

        model.fit(
            jd.astype(float),
            mag_dc,
            err_dc,
            pdf['i:fid'].astype(int)
        )

        if fit_period:
            period = model.best_period
        else:
            period = manual_period

        phase = jd.astype(float).values % period
        tfit = np.linspace(0, period, 100)

        layout_phase_ = copy.deepcopy(layout_phase)
        layout_phase_['title']['text'] = 'Period: {} days'.format(period)

        if '1' in np.unique(pdf['i:fid'].values):
            plot_filt1 = {
                'x': phase[pdf['i:fid'] == '1'],
                'y': mag_dc[pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '1'],
                    'visible': True,
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'text': phase[pdf['i:fid'] == '1'],
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            }
            fit_filt1 = {
                'x': tfit,
                'y': model.predict(tfit, period=period, filts=1),
                'mode': 'lines',
                'name': 'fit g band',
                'showlegend': False,
                'line': {
                    'color': '#1f77b4',
                }
            }
        else:
            plot_filt1 = {}
            fit_filt1 = {}

        if '2' in np.unique(pdf['i:fid'].values):
            plot_filt2 = {
                'x': phase[pdf['i:fid'] == '2'],
                'y': mag_dc[pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '2'],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'text': phase[pdf['i:fid'] == '2'],
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
            fit_filt2 = {
                'x': tfit,
                'y': model.predict(tfit, period=period, filts=2),
                'mode': 'lines',
                'name': 'fit r band',
                'showlegend': False,
                'line': {
                    'color': '#ff7f0e',
                }
            }
        else:
            plot_filt2 = {}
            fit_filt2 = {}

        figure = {
            'data': [
                plot_filt1,
                fit_filt1,
                plot_filt2,
                fit_filt2
            ],
            "layout": layout_phase_
        }
        return figure
    return {'data': [], "layout": layout_phase}

@app.callback(
    [
        Output('mulens_plot', 'figure'),
        Output('mulens_params', 'children'),
    ],
    [
        Input('submit_mulens', 'n_clicks'),
        Input('object-data', 'children')
    ])
def plot_mulens(n_clicks, object_data):
    """ Fit for microlensing event

    TODO: implement a fit using pyLIMA
    """
    if n_clicks is not None:
        pdf_ = pd.read_json(object_data)
        cols = [
            'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
            'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos', 'i:objectId'
        ]
        pdf = pdf_.loc[:, cols]
        pdf['i:fid'] = pdf['i:fid'].astype(str)
        pdf = pdf.sort_values('i:jd', ascending=False)

        mag_dc, err_dc = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:fid'].astype(int).values,
                    pdf['i:magpsf'].astype(float).values,
                    pdf['i:sigmapsf'].astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:magzpsci'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )

        # Container for measurements
        subpdf = pd.DataFrame({
            'filtercode': [],
            'mag_g': [],
            'magerr_g': [],
            'mag_r': [],
            'magerr_r': [],
            'time': [],
            'name': []
        })

        # Loop over filters
        conversiondict = {1.0: 'g', 2.0: 'r'}
        fids = pdf['i:fid'].astype(int).values
        jds = pdf['i:jd'].astype(float)
        jds_ = jds.values
        magpsf = pdf['i:magpsf'].astype(float).values

        # extract historical and current measurements
        subpdf['time'] = jds_
        subpdf['name'] = pdf['i:objectId']

        masks = {'1': [], '2': []}
        filts = []
        for fid in np.unique(fids):
            # Select filter
            mask_fid = fids == fid

            # Remove upper limits
            maskNone = np.array(magpsf) == np.array(magpsf)

            # Remove outliers
            maskOutlier = np.array(mag_dc) < 22

            # Total mask
            mask = mask_fid * maskNone * maskOutlier
            masks[str(fid)] = mask

            # mot enough points for the fit
            if np.sum(mask) < 4:
                continue

            # Gather data for the fitter
            subpdf['filtercode'] = pd.Series(fids).replace(to_replace=conversiondict)
            subpdf[f'mag_{conversiondict[fid]}'] = mag_dc
            subpdf[f'magerr_{conversiondict[fid]}'] = err_dc

            # Nullify data which is not this filter
            subpdf[f'magerr_{conversiondict[fid]}'][~mask] = None
            subpdf[f'mag_{conversiondict[fid]}'][~mask] = None

            filts.append(str(fid))

        results_ml = fit_ml_de_simple(subpdf)

        # Compute chi2
        nfitted_param = 4. # u0, t0, tE, magstar
        time = np.arange(np.min(jds_), np.max(jds_), 1)

        if '1' in filts:
            plot_filt1 = {
                'x': jds[pdf['i:fid'] == '1'].apply(lambda x: convert_jd(float(x), to='iso')),
                'y': mag_dc[pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '1'],
                    'visible': True,
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'text': jds_[pdf['i:fid'] == '1'],
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            }
            fit_filt1 = {
                'x': [convert_jd(float(t), to='iso') for t in time],
                'y': mulens_simple(time, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_g),
                'mode': 'lines',
                'name': 'fit g band',
                'showlegend': False,
                'line': {
                    'color': '#1f77b4',
                }
            }

            # chi2
            observed = mag_dc[masks['1']]
            expected = mulens_simple(jds_, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_g)[masks['1']]
            err = err_dc[masks['1']]
            chi2_g = 1. / (len(observed) - nfitted_param) * np.sum((observed - expected)**2/err**2)
        else:
            plot_filt1 = {}
            fit_filt1 = {}
            chi2_g = None

        if '2' in filts:
            plot_filt2 = {
                'x': jds[pdf['i:fid'] == '2'].apply(lambda x: convert_jd(float(x), to='iso')),
                'y': mag_dc[pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '2'],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'text': jds_[pdf['i:fid'] == '2'],
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
            fit_filt2 = {
                'x': [convert_jd(float(t), to='iso') for t in time],
                'y': mulens_simple(time, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_r),
                'mode': 'lines',
                'name': 'fit r band',
                'showlegend': False,
                'line': {
                    'color': '#ff7f0e',
                }
            }

            observed = mag_dc[masks['2']]
            expected = mulens_simple(jds_, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_r)[masks['2']]
            err = err_dc[masks['2']]
            chi2_r = 1. / (len(observed) - nfitted_param) * np.sum((observed - expected)**2/err**2)
        else:
            plot_filt2 = {}
            fit_filt2 = {}
            chi2_r = None

        figure = {
            'data': [
                plot_filt1,
                fit_filt1,
                plot_filt2,
                fit_filt2
            ],
            "layout": layout_mulens
        }

        mulens_params = """
        ```python
        # Fitted parameters
        t0: {} (jd)
        tE: {} (days)
        u0: {}
        chi2_g/dof: {}
        chi2_r/dof: {}
        ```
        ---
        """.format(results_ml.t0, results_ml.tE, results_ml.u0, chi2_g, chi2_r)
        return figure, mulens_params

    mulens_params = """
    ```python
    # Fitted parameters
    t0:
    tE:
    u0:
    chi2_g/dof:
    chi2_r/dof:
    ```
    ---
    """
    return {'data': [], "layout": layout_mulens}, mulens_params

@app.callback(
    Output('aladin-lite-div', 'run'), Input('object-data', 'children'))
def integrate_aladin_lite(object_data):
    """ Integrate aladin light in the 2nd Tab of the dashboard.

    the default parameters are:
        * PanSTARRS colors
        * FoV = 0.02 deg
        * SIMBAD catalig overlayed.

    Callbacks
    ----------
    Input: takes the alert ID
    Output: Display a sky image around the alert position from aladin.

    Parameters
    ----------
    alert_id: str
        ID of the alert
    """
    pdf_ = pd.read_json(object_data)
    cols = ['i:jd', 'i:ra', 'i:dec']
    pdf = pdf_.loc[:, cols]
    pdf = pdf.sort_values('i:jd', ascending=False)

    # Coordinate of the current alert
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]

    # Javascript. Note the use {{}} for dictionary
    img = """
    var aladin = A.aladin('#aladin-lite-div',
              {{
                survey: 'P/PanSTARRS/DR1/color/z/zg/g',
                fov: 0.025,
                target: '{} {}',
                reticleColor: '#ff89ff',
                reticleSize: 32
    }});
    var cat = 'https://axel.u-strasbg.fr/HiPSCatService/Simbad';
    var hips = A.catalogHiPS(cat, {{onClick: 'showTable', name: 'Simbad'}});
    aladin.addCatalog(hips);
    """.format(ra0, dec0)

    # img cannot be executed directly because of formatting
    # We split line-by-line and remove comments
    img_to_show = [i for i in img.split('\n') if '// ' not in i]

    return " ".join(img_to_show)
