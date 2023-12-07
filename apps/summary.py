# Copyright 2020-2022 AstroLab Software
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
import dash
from dash import html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate

import dash_bootstrap_components as dbc
import visdcc
import plotly.graph_objects as go
import dash_mantine_components as dmc
from dash_iconify import DashIconify

import pandas as pd
import numpy as np
import requests

import rocks

from app import app

from apps.supernovae.cards import card_sn_scores
from apps.varstars.cards import card_explanation_variable, card_variable_button
from apps.mulens.cards import card_explanation_mulens
from apps.mulens.cards import card_mulens_button
from apps.sso.cards import card_sso_left

from apps.cards import card_lightcurve_summary
from apps.cards import card_id
from apps.cards import create_external_links, create_external_links_brokers

from apps.plotting import draw_sso_lightcurve, draw_sso_astrometry, draw_sso_residual
from apps.plotting import draw_tracklet_lightcurve, draw_tracklet_radec
from apps.plotting import plot_classbar
from apps.plotting import all_radio_options

from apps.utils import format_hbase_output
from apps.utils import get_miriade_data
from apps.utils import pil_to_b64
from apps.utils import generate_qr
from apps.utils import class_colors
from apps.utils import retrieve_oid_from_metaname
from apps.utils import loading
from fink_utils.photometry.utils import is_source_behind

from fink_utils.xmatch.simbad import get_simbad_labels

from app import APIURL

dcc.Location(id='url', refresh=False)

def tab1_content(pdf, extra_div):
    """ Summary tab
    """
    tab1_content_ = html.Div([
        dmc.Space(h=10),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(
                        style={
                            'width': '100%',
                            'height': '4pc'
                        },
                        config={'displayModeBar': False},
                        id='classbar'
                    ),
                    width=12
                ),
            ], justify='around'
        ),
        dbc.Row([
            dbc.Col([extra_div, loading(card_lightcurve_summary())], md=8),
            dbc.Col(card_id(pdf), md=4)
        ], className='g-1'),
    ])

    out = tab1_content_

    return out

def tab2_content():
    """ Supernova tab
    """
    tab2_content_ = html.Div([
        dmc.Space(h=10),
        dbc.Row([
            dbc.Col(card_sn_scores(), md=8),
            dbc.Col(id='card_sn_properties', md=4)
        ]),
    ])
    return tab2_content_

def tab3_content():
    """ Variable stars tab
    """
    nterms_base = dmc.Container(
        [
            dbc.Label("Number of base terms"),
            dbc.Input(
                placeholder="1",
                value=1,
                type="number",
                id='nterms_base',
                debounce=True,
                min=0, max=4
            ),
            dbc.Label("Number of band terms"),
            dbc.Input(
                placeholder="1",
                value=1,
                type="number",
                id='nterms_band',
                debounce=True,
                min=0, max=4
            ),
            dbc.Label("Set manually the period (days)"),
            dbc.Input(
                placeholder="Optional",
                value=None,
                type="number",
                id='manual_period',
                debounce=True
            )
        ], className='mb-3'#, style={'width': '100%', 'display': 'inline-block'}
    )

    submit_varstar_button = dmc.Button(
        'Fit data',
        id='submit_variable',
        color='dark', variant="outline", fullWidth=True, radius='xl',
        loaderProps={'variant': 'dots'}
    )

    card2 = dmc.Paper(
        [
            nterms_base,
        ], radius='sm', p='xs', shadow='sm', withBorder=True
    )

    tab3_content_ = html.Div([
        dmc.Space(h=10),
        dbc.Row([
            dbc.Col(
                loading(
                    dmc.Paper(
                        [
                            html.Div(id='variable_plot'),
                            html.Br(),
                            card_explanation_variable()
                        ], radius='xl', p='md', shadow='xl', withBorder=True
                    )
                ), md=8
            ),
            dbc.Col(
                [
                    html.Div(id="card_variable_button"),
                    html.Br(),
                    card2,
                    html.Br(),
                    submit_varstar_button
                ], md=4
            )
        ]),
    ])
    return tab3_content_

def tab4_content():
    """ Microlensing tab
    """
    submit_mulens_button = dmc.Button(
        'Fit data',
        id='submit_mulens',
        color='dark', variant="outline", fullWidth=True, radius='xl',
        loaderProps={'variant': 'dots'}
    )

    tab4_content_ = html.Div([
        dmc.Space(h=10),
        dbc.Row([
            dbc.Col(
                loading(
                    dmc.Paper(
                        [
                            html.Div(id='mulens_plot'),
                            html.Br(),
                            card_explanation_mulens()
                        ], radius='xl', p='md', shadow='xl', withBorder=True
                    )
                ), md=8
            ),
            dbc.Col(
                [
                    html.Div(id="card_mulens_button"),
                    html.Br(),
                    html.Div(id='mulens_params'),
                    html.Br(),
                    submit_mulens_button
                ], md=4
            )
        ]),
    ])
    return tab4_content_

@app.callback(
    Output("tab_sso", "children"),
    [
        Input('object-sso', 'children'),
    ]
)
def tab5_content(object_soo):
    """ SSO tab
    """
    pdf = pd.read_json(object_soo)
    if pdf.empty:
        ssnamenr = 'null'
    else:
        ssnamenr = pdf['i:ssnamenr'].values[0]

    msg = """
    Alert data from ZTF, with ephemerides provided by the
    [Miriade ephemeride service](https://ssp.imcce.fr/webservices/miriade/api/ephemcc/).
    """
    tab1 = dbc.Row(
        [
            dbc.Col(
                [
                    dmc.Space(h=10),
                    draw_sso_lightcurve(pdf),
                    html.Br(),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                [
                                    dmc.AccordionControl("Information"),
                                    dmc.AccordionPanel(dcc.Markdown(msg)),
                                ],
                                value='info'
                            ),
                        ],
                    )
                ]
            ),
        ]
    )

    tab2 = dbc.Row(
        [
            dbc.Col(
                [
                    dmc.Space(h=10),
                    draw_sso_astrometry(pdf),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                [
                                    dmc.AccordionControl("How are computed the residuals?"),
                                    dmc.AccordionPanel(dcc.Markdown("The residuals are the difference between the alert positions and the positions returned by the [Miriade ephemeride service](https://ssp.imcce.fr/webservices/miriade/api/ephemcc/)."),),
                                ],
                                value="residuals"
                            ),
                        ],
                    )
                ]
            ),
        ]
    )

    msg_phase = """
    By default, the data is modeled after the three-parameter H, G1, G2 magnitude phase function for asteroids
    from [Muinonen et al. 2010](https://doi.org/10.1016/j.icarus.2010.04.003).
    We use the implementation in [sbpy](https://sbpy.readthedocs.io/en/latest/sbpy/photometry.html#disk-integrated-phase-function-models) to fit the data.

    We propose two cases, one fitting bands separately, and
    the other combining into a common V band before fitting. We
    also propose different phase curve modeling using the HG, HG12 and HG1G2 models.
    In addition, you can fit for spin values on top of the HG1G2 model (SHG1G2, paper in prep!).
    Note that in the spin case, H, $G_1$, and $G_2$ are fitted per band, but the spin parameters
    (R, $\alpha_0$, $\beta_0$) are fitted on all bands simultaneously.
    The title displays the value for the reduced $\chi^2$ of the fit.
    Hit buttons to see the fitted values!
    """

    tab3 = dbc.Row(
        [
            dbc.Col(
                [
                    dmc.Space(h=10),
                    html.Div(id='sso_phasecurve'),
                    html.Br(),
                    dbc.Row(
                        dbc.Col(
                            dmc.ChipGroup(
                                [
                                    dmc.Chip(x, value=x, variant="outline", color="orange", radius="xl", size="sm")
                                    for x in ['per-band', 'combined']
                                ],
                                id="switch-phase-curve-band",
                                value="per-band",
                                spacing="xl",
                                position='center',
                                multiple=False,
                            )
                        )
                    ),
                    dbc.Row(
                        dbc.Col(
                            dmc.ChipGroup(
                                [
                                    dmc.Chip(x, value=x, variant="outline", color="orange", radius="xl", size="sm")
                                    for x in ['SHG1G2', 'HG1G2', 'HG12', 'HG']
                                ],
                                id="switch-phase-curve-func",
                                value="HG1G2",
                                spacing="xl",
                                position='center',
                                multiple=False,
                            )
                        )
                    ),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                [
                                    dmc.AccordionControl("How is modeled the phase curve?"),
                                    dmc.AccordionPanel(dcc.Markdown(msg_phase),),
                                ],
                                value='phase_curve'
                            ),
                        ],
                    )
                ]
            ),
        ]
    )

    if ssnamenr != 'null':
        left_side = dbc.Col(
            dmc.Tabs(
                [
                    dmc.TabsList(
                        [
                            dmc.Tab("Lightcurve", value="Lightcurve"),
                            dmc.Tab("Astrometry", value="Astrometry"),
                            dmc.Tab("Phase curve", value="Phase curve")
                        ]
                    ),
                    dmc.TabsPanel(tab1, value="Lightcurve"),
                    dmc.TabsPanel(tab2, value="Astrometry"),
                    dmc.TabsPanel(tab3, value="Phase curve")
                ], variant="outline", value="Lightcurve"
            ), md=8
        )
    else:
        msg = """
        Object not referenced in the Minor Planet Center
        """
        left_side = dbc.Col([html.Br(), dbc.Alert(msg, color="danger")], md=8)

    tab5_content_ = dbc.Row(
        [
            dmc.Space(h=10),
            left_side,
            dbc.Col(
                [
                    card_sso_left(ssnamenr)
                ], md=4
            )
        ]
    )
    return tab5_content_

@app.callback(
    Output("tab_tracklet", "children"),
    [
        Input('object-tracklet', 'children'),
    ]
)
def tab6_content(object_tracklet):
    """ Tracklet tab
    """
    pdf = pd.read_json(object_tracklet)
    tab6_content_ = html.Div([
        dmc.Space(h=10),
        dbc.Row(
            [
                dbc.Col(
                    [
                        draw_tracklet_lightcurve(pdf),
                        html.Br(),
                        draw_tracklet_radec(pdf)
                    ]
                ),
            ]
        ),
    ])
    return tab6_content_

def tabs(pdf):
    distnr = pdf['i:distnr'].values[0]
    if is_source_behind(distnr):
        extra_div = dbc.Alert(
            "It looks like there is a source behind. You might want to check the DC magnitude instead.",
            dismissable=True,
            is_open=True,
            color="light"
        )
    else:
        extra_div = html.Div()
    tabs_ = dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.Tab("Summary", value="Summary"),
                    dmc.Tab("Supernovae", value="Supernovae"),
                    dmc.Tab("Variable stars", value="Variable stars"),
                    dmc.Tab("Microlensing", value="Microlensing"),
                    dmc.Tab("Solar System", value="Solar System", disabled=not is_sso(pdf)),
                    dmc.Tab("Tracklets", value="Tracklets", disabled=not is_tracklet(pdf)),
                    dmc.Tab("GRB", value="GRB", disabled=True)
                ], position='right'
            ),
            dmc.TabsPanel(tab1_content(pdf, extra_div), value="Summary"),
            dmc.TabsPanel(tab2_content(), value="Supernovae"),
            dmc.TabsPanel(tab3_content(), value="Variable stars"),
            dmc.TabsPanel(tab4_content(), value="Microlensing"),
            dmc.TabsPanel(id="tab_sso", value="Solar System"),
            dmc.TabsPanel(id="tab_tracklet", value="Tracklets"),
        ], value="Summary"
    )

    return tabs_

def is_sso(pdfs):
    """Auxiliary function to check whether the object is a SSO"""
    payload = pdfs['i:ssnamenr'].values[0]
    if str(payload) == 'null' or str(payload) == 'None':
        return False

    if np.alltrue([i == payload for i in pdfs['i:ssnamenr'].values]):
        return True

    return False

def is_tracklet(pdfs):
    """Auxiliary function to check whether the object is a tracklet"""
    payload = pdfs['d:tracklet'].values[0]

    if str(payload).startswith('TRCK'):
        return True

    return False

@app.callback(
    Output('external_links', 'children'),
    Input('object-data', 'children')
)
def create_external_links_(object_data):
    """ Create links to external website. Used in the mobile app.
    """
    pdf = pd.read_json(object_data)
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]
    buttons = create_external_links(ra0, dec0)
    return buttons

@app.callback(
    Output('external_links_brokers', 'children'),
    Input('object-data', 'children')
)
def create_external_links_brokers_(object_data):
    """ Create links to external website. Used in the mobile app.
    """
    pdf = pd.read_json(object_data)
    buttons = create_external_links_brokers(pdf['i:objectId'].values[0])
    return buttons

@app.callback(
    [
        Output('object-data', 'children'),
        Output('object-upper', 'children'),
        Output('object-uppervalid', 'children'),
        Output('object-sso', 'children'),
        Output('object-tracklet', 'children'),
    ],
    [
        Input('url', 'pathname'),
    ])
def store_query(name):
    """ Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    if not name[1:].startswith('ZTF'):
        # check this is not a name generated by a user
        oid = retrieve_oid_from_metaname(name[1:])
        if oid is None:
            raise PreventUpdate
    else:
        oid = name[1:]

    r = requests.post(
        '{}/api/v1/objects'.format(APIURL),
        json={
            'objectId': oid,
            'withupperlim': True,
            'withcutouts': False,
        }
    )

    pdf = pd.read_json(
        r.content,
        dtype={'i:ssnamenr':str} # Force reading this field as string
    )

    pdf['i:ssnamenr'].replace('None', 'null', inplace=True) # For backwards compatibility

    pdfs = pdf[pdf['d:tag'] == 'valid']
    pdfsU = pdf[pdf['d:tag'] == 'upperlim']
    pdfsUV = pdf[pdf['d:tag'] == 'badquality']

    payload = pdfs['i:ssnamenr'].values[0]
    is_sso = np.alltrue([i == payload for i in pdfs['i:ssnamenr'].values])
    if str(payload) != 'null' and is_sso:
        r = requests.post(
            '{}/api/v1/sso'.format(APIURL),
            json={
                'n_or_d': payload,
            }
        )

        pdfsso = pd.read_json(r.content)

        if pdfsso.empty:
            # This can happen for SSO candidate with a ssnamenr
            # e.g. ZTF21abatnkh
            pdfsso = pd.DataFrame()
        else:
            # Extract miriade information as well
            name = rocks.id(payload)[0]
            pdfsso['i:ssnamenr'] = name
            pdfsso = get_miriade_data(pdfsso)
    else:
        pdfsso = pd.DataFrame()

    payload = pdfs['d:tracklet'].values[0]

    if str(payload).startswith('TRCK'):
        r = requests.post(
            '{}/api/v1/tracklet'.format(APIURL),
            json={
                'id': payload,
            }
        )

        pdftracklet = pd.read_json(r.content)
    else:
        pdftracklet = pd.DataFrame()
    return pdfs.to_json(), pdfsU.to_json(), pdfsUV.to_json(), pdfsso.to_json(), pdftracklet.to_json()

@app.callback(
    Output('qrcode', 'children'),
    [
        Input('url', 'pathname'),
    ]
)
def make_qrcode(path):
    qrdata = "https://fink-portal.org/{}".format(path[1:])
    qrimg = generate_qr(qrdata)

    return html.Img(src="data:image/png;base64, " + pil_to_b64(qrimg))

def layout(name):
    # even if there is one object ID, this returns  several alerts
    r = requests.post(
        '{}/api/v1/objects'.format(APIURL),
        json={
            'objectId': name[1:],
        }
    )
    pdf = pd.read_json(r.content)

    if pdf.empty:
        layout_ = html.Div(
            [
                dmc.Center(
                    style={"height": "100%", "width": "100%"},
                    children=[
                        dbc.Alert("{} not found. Either the object name does not exist, or it has not yet been injected in our database (nightly data appears at the end of the night).".format(name[1:]), color="danger"),
                    ],
                )
            ], className="bg-opaque-60"
        )
    else:
        layout_ = html.Div(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(id="card_id_left", className="p-1", lg=12, md=6, sm=12),
                                    dbc.Col(
                                        html.Div(
                                            [visdcc.Run_js(id='aladin-lite-div')],
                                            style={
                                                'width': '100%',
                                                'height': '27pc',
                                            },
                                            className="p-1 d-none d-md-block"
                                        ), lg=12, md=6, sm=12
                                    )
                                ],
                                className="g-0"
                            ), lg=3, className="p-1"
                        ),
                        dbc.Col(
                            [
                                dmc.Space(h=10),
                                tabs(pdf),
                            ],
                            lg=9, className="p-1"
                        )
                    ],
                    justify="around", className="g-0"
                ),
                html.Div(id='object-data', style={'display': 'none'}),
                html.Div(id='object-upper', style={'display': 'none'}),
                html.Div(id='object-uppervalid', style={'display': 'none'}),
                html.Div(id='object-sso', style={'display': 'none'}),
                html.Div(id='object-tracklet', style={'display': 'none'}),
            ], className='bg-opaque-90'
        )

    return layout_
