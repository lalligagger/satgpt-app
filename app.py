# from agent import agent_executor
from mapper import MapManager
from tools import StacSearchTool

from ipyleaflet import Map, Marker
import json
from odc import ui
from odc.stac import stac_load
from odc import ui
from odc.algo import colorize, to_rgba
import panel as pn
import pystac
from pystac_client.client import Client

import panel as pn
from langchain.callbacks.base import BaseCallbackHandler

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.chat_models import ChatOpenAI

from langchain import OpenAI
from langchain.tools import BaseTool, StructuredTool
from langchain.agents import initialize_agent, AgentType
from typing import Tuple, Optional

import param
import pandas as pd
import time

pn.extension("terminal", sizing_mode="stretch_width", design="bootstrap")

# default user request
user_req = 'Sentinel images available over Seattle in August 2022'

StacSearchTool.name = "stacsearch"
StacSearchTool.description =  """
    query the STAC API, using pystac-client, once the bounding box and date range are known
    given bounding box 'bbox', (tuple), and optionally:
    - date range: 'dtime' (str)
    - api catalog: 'url', (str)
    - stac query (e.g. ["eo:cloud_cover<30", ...]): 'q', (list)
"""

class ChatStreamCallbackHandler(BaseCallbackHandler):
    """A basic Call Back Handler that will update the token on the chat widget provided"""

    def __init__(self, chat: "ChatWidget"):
        self.chat = chat

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.chat.token = token

class ChatWidget(pn.viewable.Viewer):
    text: str = param.String(
        default=user_req,
        doc="""The text to submit to the chat api""",
    )
    submit: bool = param.Event(label="SUBMIT")

    token: str = param.String(doc="""The single token streamed from the chat api""")
    value: str = param.String()

    is_predicting: bool = param.Boolean(
        default=False, doc="""True while the chat is predicting"""
    )

    max_tokens = param.Integer(
        default=1500,
        bounds=(1, 2000),
        doc="""The maximum number of tokens returned by the chat api""",
    )
    streaming = param.Boolean(
        default=True, doc="""Whether or not to stream the tokens"""
    )

    def __init__(self, **params):
        super().__init__(**params)
        self._create_panel()
        self._create_chat()

    def __panel__(self):
        return self._panel

    def _create_panel(self):
        self._terminal = pn.widgets.Terminal(height=250)
        pn.bind(self._terminal.write, self.param.token, watch=True)

        self._submit_button = pn.widgets.Button.from_param(
            self.param.submit, button_type="primary", icon="robot"
        )
        self._text_input = pn.widgets.TextAreaInput.from_param(self.param.text)
        
        ## TODO: could use for e.g. opacity, display resolution
        # self._show_settings = pn.widgets.Checkbox(value=False, name="Show settings?")
        # self._settings = pn.Column(
        #     self.param.max_tokens,
        #     visible=self._show_settings,
        # )
        
        self._panel = pn.Column(
            # "### Input",
            # self._show_settings,
            # self._settings,ß
            self._text_input,
            self._submit_button,
            # "### Output",
            pn.Accordion(('<span style="color:red; font-size:.5em;">Debug</span>', self._terminal))
        )

    @pn.depends("max_tokens", "streaming", watch=True)
    def _create_chat(self):
        stream_handler = ChatStreamCallbackHandler(chat=self)
        llm = OpenAI(
            temperature=0,
            max_tokens=self.max_tokens,
            streaming=self.streaming,
            callbacks=[stream_handler],
        )

        # Structured tools are compatible with the STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION agent type. 
        self._chat = initialize_agent(
            tools=[StacSearchTool()], 
            llm=llm, 
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION, 
            streaming=False,
            verbose=True,
            # memory = conversational_memory
            )

    @pn.depends("is_predicting", watch=True)
    def _handle_predicting(self):
        self.param.submit.constant = self.is_predicting

    @pn.depends("submit", watch=True)
    async def apredict(self):
        self.is_predicting = True

        self.value = self._chat.run(self.text)

        ## TODO: Get full async runs working. Right now get error about bbox args being passed to _run
        # File "/home/codespace/.local/lib/python3.10/site-packages/langchain/tools/base.py", line 330, in arun
        #     await self._arun(*tool_args, run_manager=run_manager, **tool_kwargs)
        # File "/workspaces/satgpt-app/langchain_tools.py", line 76, in _arun
        #     self._run(
        # TypeError: StacSearchTool._run() got multiple values for argument 'bbox'
        
        # self.value = await self._chat.arun(self.text)

        self.is_predicting = False

        if self._terminal:
            self._terminal.writelines(lines=["\n\n", "-", "\n\n"])


token_map = {}
chat = ChatWidget()

map_mgr = MapManager()
button = pn.widgets.Button(name='Update Items to Map', button_type='warning')
pn.extension("ipywidgets", sizing_mode="stretch_width")

ACCENT_BASE_COLOR = "#DAA520"

@pn.depends(button, watch=True)
def update_items(clicks):
    map_mgr.load_items()

component = pn.Column(
    chat,
    button,
    map_mgr.panel,
)

template = pn.template.FastListTemplate(
    # site="Awesome Panel",
    title="SatGPT",
    logo="https://panel.holoviz.org/_static/logo_stacked.png",
    header_background=ACCENT_BASE_COLOR,
    accent_base_color=ACCENT_BASE_COLOR,
    main=[component],
).servable()