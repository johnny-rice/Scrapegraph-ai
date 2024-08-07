"""
SearchLinkNode Module
"""

# Imports from standard library
from typing import List, Optional
import re
from tqdm import tqdm

# Imports from Langchain
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableParallel

from ..utils.logging import get_logger

# Imports from the library
from .base_node import BaseNode


class SearchLinkNode(BaseNode):
    """
    A node that can filter out the relevant links in the webpage content for the user prompt.
    Node expects the already scrapped links on the webpage and hence it is expected
    that this node be used after the FetchNode.

    Attributes:
        llm_model: An instance of the language model client used for generating answers.
        verbose (bool): A flag indicating whether to show print statements during execution.

    Args:
        input (str): Boolean expression defining the input keys needed from the state.
        output (List[str]): List of output keys to be updated in the state.
        node_config (dict): Additional configuration for the node.
        node_name (str): The unique identifier name for the node, defaulting to "GenerateAnswer".
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "GenerateLinks",
    ):
        super().__init__(node_name, "node", input, output, 1, node_config)

        self.llm_model = node_config["llm_model"]
        self.verbose = (
            False if node_config is None else node_config.get("verbose", False)
        )

    def execute(self, state: dict) -> dict:
        """
        Filter out relevant links from the webpage that are relavant to prompt. Out of the filtered links, also
        ensure that all links are navigable.

        Args:
            state (dict): The current state of the graph. The input keys will be used to fetch the
                            correct data types from the state.

        Returns:
            dict: The updated state with the output key containing the list of links.

        Raises:
            KeyError: If the input keys are not found in the state, indicating that the
                        necessary information for generating the answer is missing.
        """

        self.logger.info(f"--- Executing {self.node_name} Node ---")


        parsed_content_chunks = state.get("doc")
        output_parser = JsonOutputParser()

        relevant_links = []

        for i, chunk in enumerate(
            tqdm(
                parsed_content_chunks,
                desc="Processing chunks",
                disable=not self.verbose,
            )
        ):
            try:
                # Primary approach: Regular expression to extract links
                links = re.findall(r'https?://[^\s"<>\]]+', str(chunk.page_content))

                relevant_links += links
            except Exception as e:
                # Fallback approach: Using the LLM to extract links
                self.logger.error(f"Error extracting links: {e}. Falling back to LLM.")
                prompt_relevant_links = """
                    You are a website scraper and you have just scraped the following content from a website.
                    Content: {content}
                    
                    Assume relevance broadly, including any links that might be related or potentially useful 
                    in relation to the task.

                    Sort it in order of importance, the first one should be the most important one, the last one
                    the least important
                    
                    Please list only valid URLs and make sure to err on the side of inclusion if it's uncertain 
                    whether the content at the link is directly relevant.

                    Output only a list of relevant links in the format:
                    [
                        "link1",
                        "link2",
                        "link3",
                        .
                        .
                        .
                    ]
                    """
                
                merge_prompt = PromptTemplate(
                    template=prompt_relevant_links,
                    input_variables=["content", "user_prompt"],
                )
                merge_chain = merge_prompt | self.llm_model | output_parser
                answer = merge_chain.invoke(
                    {"content": chunk.page_content}
                )
                relevant_links += answer

        state.update({self.output[0]: relevant_links})
        return state
