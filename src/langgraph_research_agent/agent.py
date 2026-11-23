from .utils.states import ResearchGraphState
from .utils.nodes import create_analysts, human_feedback, write_report, write_introduction, write_conclusion, finalise_report
from .utils.edges import initiate_all_interviews
from langgraph.graph import START, END, StateGraph
from .answering_questions import interview_builder

builder = StateGraph(ResearchGraphState)

builder.add_node("create_analysts", create_analysts)
builder.add_node("human_feedback", human_feedback)
builder.add_node("conduct_interview", interview_builder.compile())
builder.add_node("write_report", write_report)
builder.add_node("write_introduction", write_introduction)
builder.add_node("write_conclusion", write_conclusion)
builder.add_node("finalise_report", finalise_report)

builder.add_edge(START, "create_analysts")
builder.add_edge("create_analysts", "human_feedback")
builder.add_conditional_edges("human_feedback", initiate_all_interviews, ["create_analysts", "conduct_interview"])
builder.add_edge("conduct_interview", "write_report")
builder.add_edge("conduct_interview", "write_introduction")
builder.add_edge("conduct_interview", "write_conclusion")
builder.add_edge(["write_report", "write_introduction", "write_conclusion"], "finalise_report")
builder.add_edge("finalise_report", END)

graph = builder.compile()