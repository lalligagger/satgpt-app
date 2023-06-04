import json
from langchain import OpenAI
from langchain.agents import initialize_agent#, AgentType
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.tools import StructuredTool
from pystac_client.client import Client
from typing import Tuple, Optional


# tool 1 - done
# saves stac items to tmp/items.json
# working... with one issue: bbox needs to be passed to tool2
def stacsearch(
    bbox: Tuple[float, float, float, float],
    dtime: Optional[str],
    url: Optional[str]='https://earth-search.aws.element84.com/v1/',
    savepath: Optional[str] = './tmp/items.json',
    # q: Optional[list] = ["eo:cloud_cover<30"]
    ) -> str:

    """
    query the STAC API, using pystac-client, once the bounding box and date range are known
    given bounding box 'bbox', (tuple), and optionally:
    - date range: 'dtime' (str)
    - api catalog: 'url', (str)
    """
    # - stac query (e.g. ["eo:cloud_cover<30", ...]): 'q', (list) # TODO: add back
    # no collections input is needed - we have fixed to E84 sentinel-2-l2a for now

    client = Client.open(url)

    query = client.search(
    max_items=10,
    collections=['sentinel-2-l2a'],
    bbox=bbox,
    # TODO: re-term query above and test LLM query inputs below
    query=["eo:cloud_cover<30"],
    datetime=dtime
    )

    items_dict = query.get_all_items_as_dict()

    with open('./items.json', 'w') as f:
        f.write(json.dumps(items_dict, indent=2))
    
    return f"{query.matched()} items were found & saved to {savepath}"

# tool 2 - TODO
# def map_item
# bbox = (0,0,0,0)

# print(bbox)

STACSearch = StructuredTool.from_function(stacsearch)