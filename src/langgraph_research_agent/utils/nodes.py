from dotenv import load_dotenv
from .states import GeneratedAnalystsState, InterviewState, ResearchGraphState
from .models import llm
from .objects import Analyst, Perspectives, SearchQuery
from .prompts import analyst_instructions, question_instructions, search_instructions, answer_instructions, section_writer_instructions, report_writer_instructions, intro_conclusion_instructions
from langchain.messages import SystemMessage, HumanMessage
from langgraph.types import interrupt
from langchain_tavily import TavilySearch
from langchain_core.messages import get_buffer_string

load_dotenv()

def create_analysts(state: GeneratedAnalystsState):
    """Create analysts"""
    topic = state["topic"]
    max_analysts = state["max_analysts"]
    human_analyst_feedback = state.get("human_analyst_feedback", "")

    # enforce structured output
    structured_llm = llm.with_structured_output(Perspectives)

    system_message = analyst_instructions.format(topic=topic,
                                                 max_analysts=max_analysts,
                                                 human_analyst_feedback=human_analyst_feedback)

    analysts = structured_llm.invoke([SystemMessage(content=system_message)] + [HumanMessage(content="Please generate the set of analysts")])

    return {"analysts": analysts.analysts}

def human_feedback(state: GeneratedAnalystsState):
    """Where human gives feedback on the analysts"""
    feedback = interrupt({
        "question": "Are these analysts good?",
        "analysts": [analyst.model_dump() if hasattr(analyst, "model_dump") else analyst 
                     for analyst in state.get("analysts", [])],
        "instructions": "Return feedback to regenerate analysts or return empty/perfect/continue/okay to approve and continue the graph"
    })

    if feedback is None:
        return {"human_analyst_feedback": None}

    if isinstance(feedback, str):
        feedback = feedback.strip()

        if feedback == "" or feedback.lower() in ("perfect", "okay", "continue", "yes"):
            return {"human_analyst_feedback": None}

        return {"human_analyst_feedback": feedback}

    return {"human_analyst_feedback": None}

def generate_question(state: InterviewState):
    """Node to generat ethe questions"""

    # get the state analyst
    analyst = state["analyst"]
    if isinstance(analyst, dict):
        analyst = Analyst.model_validate(analyst)

    messages = state["messages"]

    system_message = question_instructions.format(goals=analyst.persona)
    question = llm.invoke([SystemMessage(content=system_message)] + messages)

    return {"messages": [question]} #we have a reducer from import operator that automatically appends

def _tavily_results(response: dict) -> list[dict]:
    """Extract results or surface the error returned by the Tavily tool."""
    if not isinstance(response, dict):
        raise ValueError("Expected a Tavily response with a results list")

    error = response.get("error")
    if isinstance(error, Exception):
        raise error
    if error is not None:
        raise RuntimeError(f"Tavily search failed: {error}")

    results = response.get("results")
    if not isinstance(results, list):
        raise ValueError("Expected a Tavily response with a results list")
    return results

def search_web(state: InterviewState):
    """Retrieve docs from the web"""

    # search query
    structured_llm = llm.with_structured_output(SearchQuery)

    search_instructions_system_message = SystemMessage(content=search_instructions)
    tavily_search = TavilySearch(max_results=3)

    search_query = structured_llm.invoke([search_instructions_system_message] + state["messages"])

    data = tavily_search.invoke({"query": search_query.search_query})
    search_docs = _tavily_results(data)

    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]}

def search_web2(state: InterviewState):
    """Retrieve docs from the web"""

    # search query
    structured_llm = llm.with_structured_output(SearchQuery)

    search_instructions_system_message = SystemMessage(content=search_instructions)
    tavily_search = TavilySearch(max_results=3)

    search_query = structured_llm.invoke([search_instructions_system_message] + state["messages"])

    data = tavily_search.invoke({"query": search_query.search_query})
    search_docs = _tavily_results(data)

    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]}

def generate_answers(state: InterviewState):
    """Node to answer a question"""

    # get state
    analyst = state["analyst"]
    messages = state["messages"]
    context = state["context"]

    if isinstance(analyst, dict):
        analyst = Analyst.model_validate(analyst)

    # answer question
    system_message = answer_instructions.format(goals=analyst.persona, context=context)
    answer = llm.invoke([SystemMessage(content=system_message)] + messages)

    # name the message as the expert answer
    answer.name = "expert"

    return {"messages": [answer]}

def save_interview(state: InterviewState):
    """Save interviews"""

    messages = state["messages"]

    interview = get_buffer_string(messages)

    return {"interview": interview}

def write_section(state: InterviewState):
    """Node to answer a question"""

    interview = state["interview"]
    context = state["context"]
    analyst = state["analyst"]

    if isinstance(analyst, dict):
        analyst = Analyst.model_validate(analyst)

    system_message = section_writer_instructions.format(focus=analyst.description)
    section = llm.invoke([SystemMessage(content=system_message)] + 
                         [HumanMessage(content=f"Use this source to write your section: {context}")])

    return {"sections": [section.content]}

def write_report(state: ResearchGraphState):

    sections = state["sections"]
    topic = state["topic"]

    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])

    system_message = report_writer_instructions.format(topic=topic, context=formatted_str_sections)
    report = llm.invoke([SystemMessage(content=system_message)] + [HumanMessage(content="Write me a report based on these memos")])
    return {"content": report.content}

def write_introduction(state: ResearchGraphState):

    sections = state["sections"]
    topic = state["topic"]

    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])

    instructions = intro_conclusion_instructions.format(topic=topic, formatted_str_sections=formatted_str_sections)
    intro = llm.invoke([SystemMessage(content=instructions)] + [HumanMessage(content="Write the report introduction")])
    return {"introduction": intro.content}

def write_conclusion(state: ResearchGraphState):

    sections = state["sections"]
    topic = state["topic"]

    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])

    instructions = intro_conclusion_instructions.format(topic=topic, formatted_str_sections=formatted_str_sections)
    conclusion = llm.invoke([SystemMessage(content=instructions)] + [HumanMessage(content="Write the report conclusion")])
    return {"conclusion": conclusion.content}

def finalise_report(state: ResearchGraphState):
    """This is the "reduce" step where we gather all the sections, combine them, and reflect on them to finalise the report"""

    content = state["content"]

    heading, _, body = content.partition("\n")
    if heading.rstrip() == "## Insights":
        content = body.lstrip("\n")

    if "## Sources" in content:
        try:
            content, sources = content.split("\n## Sources\n")
        except:
            sources = None
    else:
        sources = None

    final_report = state["introduction"] + "\n\n---\n\n" + content + "\n\n---\n\n" + state["conclusion"]

    if sources is not None:
        final_report += "\n\n## Sources\n" + sources

    return {"final_report": final_report}
