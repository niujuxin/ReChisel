
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ReChisel.llms import get_llm_client, llm_call_with_retry
from ReChisel.chisel_code import ChiselCode
from ReChisel.testcase import Testcase
from ReChisel.verifier import VerifyResult, collect_verify_feedback


class Attempt:
    def __init__(
            self, 
            chisel_code: ChiselCode, 
            verify_result: VerifyResult,
            reviewer_response: AIMessage,
            *,
            llm_summary: str = None
    ):
        self.chisel_code = chisel_code
        self.verify_result = verify_result
        self.reviewer_response = reviewer_response
        self._llm_summary = llm_summary

    @property
    def summary(self):
        if self._llm_summary is None:
            return self.reviewer_response.content
        return self._llm_summary


class Tracing:
    def __init__(
            self, testcase: Testcase,
            *,
            use_llm_summary: bool = False,
            llm_summary_model: str = '',
            llm_summary_system_prompt: str = ""
    ):
        self.testcase = testcase
        self.attempts: list[Attempt] = []

        self._use_llm_summary = use_llm_summary
        self._llm_summary_model = llm_summary_model
        self._llm_summary_system_prompt = llm_summary_system_prompt

    def add_attempt(
            self, 
            chisel_code: ChiselCode, 
            verify_result: VerifyResult, 
            reviewer_response: AIMessage
    ):
        if not self._use_llm_summary:
            llm_summary = None
        else:
            messages = [
                SystemMessage(self._llm_summary_system_prompt),
                collect_verify_feedback(self.testcase, verify_result, chisel_code),
                HumanMessage(f"# Reviewer Response:\n\n{reviewer_response.content}")
            ]
            client = get_llm_client(self._llm_summary_model)
            response = llm_call_with_retry(client, messages)
            llm_summary = response.content
        
        trace_item = Attempt(
            chisel_code=chisel_code,
            verify_result=verify_result,
            reviewer_response=reviewer_response,
            llm_summary=llm_summary
        )
        self.attempts.append(trace_item)

    def last_k_attempts(self, k: int) -> list[Attempt]:
        if k < 0:
            return self.attempts
        return self.attempts[-k:] if k <= len(self.attempts) else self.attempts


def in_context_attempt_history_format(
        tracing: Tracing, 
        k: int = 5
) -> HumanMessage:
    """
    Format the last k trace items into a list of messages for in-context learning.
    """
    traces = [
        f"## Attempt {i + 1}\n\n"
        f"Chisel Code (omitted):\n"
        f"```scala\n{item.chisel_code.raw_stripped}\n```\n"
        f"Summary: {item.summary}\n\n"
        for i, item in enumerate(tracing.last_k_attempts(k))
    ]
    return HumanMessage(
        "Below are the most recent consecutive k attempts trying to implement this Chisel module. "
        "For each attempt, the corresponding code is provided along with a summary "
        "of the errors found in that version and the suggested modifications. \n\n"
        "NOTE: Please refer to these past attempts to avoid repeating the same mistakes.\n\n"
        + "\n".join(traces)
    )
