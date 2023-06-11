# Import things that are needed generically
# from langchain import LLMMathChain, SerpAPIWrapper
from langchain.agents import AgentType, initialize_agent
from langchain.chat_models import ChatOpenAI
from langchain.tools import BaseTool, StructuredTool, Tool, tool
from typing import Optional, Type
import asyncio
from langchain import OpenAI
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.agents import initialize_agent, AgentType
from langchain.tools import StructuredTool
from typing import Tuple, Optional
import json

from langchain import OpenAI
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.agents import initialize_agent, AgentType
from langchain.tools import StructuredTool
from typing import Tuple, Optional

from pystac_client.client import Client

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

class StacSearchTool(BaseTool):
    name = "stacsearch"
    description =  """
    query the STAC API, using pystac-client, given:
    - bbox (str), e.g. '-122.3, 47.6, -122.2, 47.7'
    - dtime (str)
    """
    # - url (str)
    # - bbox (tuple), e.g. (-122.3, 47.6, -122.2, 47.7)
    # - q (list), e.g. ["eo:cloud_cover<30", ...]: 
    # - savepath (str), e.g. './tmp/items.json'

    def _run(self,  
            # bbox: Tuple[float, float, float, float],
            bbox: str,
            dtime: Optional[str],
            savepath: Optional[str] = './tmp/items.json',
            run_manager: Optional[CallbackManagerForToolRun] = None
            ) -> str:
        """Use the tool."""
        print(bbox)
        url = 'https://earth-search.aws.element84.com/v1/'
        client = Client.open(url)

        query = client.search(
        max_items=100,
        collections=['sentinel-2-l2a'],
        bbox=bbox,
        datetime=dtime
        )

        items_dict = query.get_all_items_as_dict()

        with open(savepath, 'w') as f:
            f.write(json.dumps(items_dict, indent=2))
        
        return f"{query.matched()} items were found & saved to {savepath}"  
    
    async def _arun(
        self, 
        bbox: str,
        dtime: Optional[str],
        savepath: Optional[str] = './tmp/items.json', 
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
        ) -> str:
        """Use the tool asynchronously."""
        # bbox: Tuple[float, float, float, float],
        # raise NotImplementedError("custom_search does not support async")
        # bbox_str = str(bbox)

        print(bbox)
        return asyncio.run(
            self._run(
                self, 
                # savepath = savepath,
                bbox, 
                dtime, 
                savepath, 
                # run_manager
                )
            )
    