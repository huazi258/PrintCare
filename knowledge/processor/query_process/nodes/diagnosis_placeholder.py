"""Temporary fail-closed endpoint for the future diagnosis flow."""

from knowledge.processor.query_process.base import BaseNode
from knowledge.processor.query_process.state import QueryGraphState


class DiagnosisPlaceholderNode(BaseNode):
    """Stop an internal diagnosis graph invocation without generating an answer.

    T1-03 intentionally does not create a diagnosis result, save ordinary chat
    history, invoke an LLM, or access any external search provider.
    """

    name = "diagnosis_placeholder_node"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        state["answer"] = ""
        state["diagnosis_status"] = "not_available"
        state["diagnosis_message"] = "诊断功能尚未开放"
        return state
