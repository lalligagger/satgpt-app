from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder

# from langchain import SerpAPIWrapper
from langchain.agents import initialize_agent
from langchain.agents import AgentType, AgentExecutor
from langchain.tools import StructuredTool
from langchain.chat_models import ChatOpenAI

from typing import List, Dict
import os
import logging

import panel as pn


class _DropStaleReferenceErrors(logging.Filter):
    """Drop Bokeh's "can't resolve reference" errors.

    The image viewer rebuilds its figure on every widget change, so pan/zoom events the browser sends for the
    previous figure arrive after the server has discarded it. Bokeh logs each one as an error and ignores it.
    Harmless for the user; this keeps the terminal readable."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "can't resolve reference" not in record.getMessage()


logging.getLogger("bokeh.server.protocol_handler").addFilter(_DropStaleReferenceErrors())
import param
import pandas as pd
import geopandas as gpd

from modules.chat_utils import make_tools
# from modules.rasterize_plots import s2_hv_plot, create_rgb_viewer

pd.options.plotting.backend = 'holoviews'

pn.extension('floatpanel')

# Process-wide, read once: these hold no user data.
# gpt-3.5-turbo-0613 was retired by OpenAI; any chat model with function calling works.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SATGPT_MODEL = os.environ.get("SATGPT_MODEL", "gpt-4o-mini")


def create_app():
    """Build one visitor's app: its own MapManager/tools, agent, memory and chat box.

    `panel serve app.py` re-runs this script for every browser session, so
    everything created here (and nothing imported at module level) is
    private to that session. Nothing is written to disk.
    """
    map_mgr, tools = make_tools()

    chat_box = pn.widgets.ChatBox(ascending=True)

    llm = ChatOpenAI(temperature=0, model=SATGPT_MODEL, openai_api_key=OPENAI_API_KEY)

    agent_kwargs = {
        "extra_prompt_messages": [MessagesPlaceholder(variable_name="memory")],
    }
    memory = ConversationBufferMemory(memory_key="memory", return_messages=True)

    agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        agent_kwargs=agent_kwargs,
        memory=memory,
    )

    def chat(user_messages: List[Dict[str, str]]) -> None:
        # user_messages = [{"You": "Your input"}, {"AI": "A response"}, ...]
        user_message = user_messages[-1]
        input = user_message.get("You")
        if input is None:
            return
        try:
            text = agent.run(input=input)
        except Exception as exc:  # surface tool/LLM failures in the chat instead of a silent traceback
            text = f"Sorry, that step failed: {type(exc).__name__}: {str(exc)[:300]}"

        if map_mgr.media is not None:
            media = map_mgr.media
            chat_box.append({"SatGPT": media})
            map_mgr.media = None

        chat_box.append({"SatGPT": text})

    pn.bind(chat, user_messages=chat_box, watch=True)

    component = pn.Column(chat_box, height=800)

    template = pn.template.FastListTemplate(
        # site="Awesome Panel",
        title="SatGPT - Panel Demo App",
        logo="https://panel.holoviz.org/_static/logo_stacked.png",
        main=[component],
    )
    return template


create_app().servable()
