from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder

# from langchain import SerpAPIWrapper
from langchain.agents import initialize_agent
from langchain.agents import AgentType, AgentExecutor
from langchain.tools import StructuredTool
from langchain.chat_models import ChatOpenAI

from typing import List, Dict
import panel as pn
import param
import pandas as pd
import geopandas as gpd

from modules.chat_utils import tools, map_mgr#, chat_box
# from modules.rasterize_plots import s2_hv_plot, create_rgb_viewer

pd.options.plotting.backend = 'holoviews'

pn.extension('floatpanel')

chat_box = pn.widgets.ChatBox(ascending=True)

def chat(user_messages: List[Dict[str, str]]) -> None:
    # user_messages = [{"You": "Your input"}, {"AI": "A response"}, ...]
    user_message = user_messages[-1]
    input = user_message.get("You")
    if input is None:
        return
    text = agent.run(input=input)
    
    if map_mgr.media is not None:
        media = map_mgr.media
        chat_box.append({"SatGPT": media})
        map_mgr.media = None

    chat_box.append({"SatGPT": text})

pn.bind(chat, user_messages=chat_box, watch=True)

llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613")

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
    memory=memory
    )
component = pn.Column(chat_box, height=800)

template = pn.template.FastListTemplate(
    # site="Awesome Panel",
    title="SatGPT - Panel Demo App",
    logo="https://panel.holoviz.org/_static/logo_stacked.png",
    main=[component],
)

template.servable()