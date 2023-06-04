from langchain import OpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.tools import StructuredTool
from typing import Tuple, Optional

from tools import STACSearch as tool

llm = OpenAI(temperature=0)#, openai_api_key=OPENAI_API_KEY)

# Structured tools are compatible with the STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION agent type. 
agent_executor = initialize_agent(
    [tool], 
    llm, 
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION, 
    verbose=True,
    # memory = conversational_memory
    )