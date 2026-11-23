from .utils.nodes import create_analysts, human_feedback
from langgraph.graph import StateGraph, START, END
from .utils.states import GeneratedAnalystsState
from dotenv import load_dotenv
from .utils.edges import should_continue

load_dotenv()

# Creating the graph
# GeneratedAnalystsState state
# Nodes create_analysts
# edges 

builder = StateGraph(GeneratedAnalystsState)

builder.add_node("create_analysts", create_analysts)
builder.add_node("human_feedback", human_feedback)

builder.add_edge(START, "create_analysts")
builder.add_edge("create_analysts", "human_feedback")
builder.add_conditional_edges("human_feedback", should_continue)

graph = builder.compile()