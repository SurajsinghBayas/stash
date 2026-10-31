"""One chat turn as a LangGraph.

LangGraph owns the path: plan, then either a short reply, a search, an optional ranking
pass, the answer, and a check when the answer cites cards. The nodes stream the same
events the drawer already shows.

There is no checkpointer. A turn finishes inside one request, and the transcript is
saved in Postgres afterwards. Resuming a graph from a second database connection would
not change the answer.
"""

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class ChatState(TypedDict, total=False):
    step: Literal["chitchat", "retrieve", "rank", "answer", "verify", "end"]


AGENT_NODES = ("plan", "chitchat", "retrieve", "rank", "answer", "verify")


def _step(state: ChatState) -> str:
    return state["step"]


def build_chat_graph(conv):
    """Compile the turn. `conv` is the Conversation whose methods are the nodes."""
    graph = StateGraph(ChatState)
    graph.add_node("plan", conv.graph_plan)
    graph.add_node("chitchat", conv.graph_chitchat)
    graph.add_node("retrieve", conv.graph_retrieve)
    graph.add_node("rank", conv.graph_rank)
    graph.add_node("answer", conv.graph_answer)
    graph.add_node("verify", conv.graph_verify)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", _step, {"chitchat": "chitchat", "retrieve": "retrieve", "end": END})
    graph.add_edge("chitchat", END)
    graph.add_conditional_edges("retrieve", _step, {"rank": "rank", "answer": "answer"})
    graph.add_edge("rank", "answer")
    graph.add_conditional_edges("answer", _step, {"verify": "verify", "end": END})
    graph.add_edge("verify", END)
    return graph.compile()
