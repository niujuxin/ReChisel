

from dataclasses import dataclass
from functools import cached_property
from typing import Tuple

from rechisel.llm_client import get_model_completion
from rechisel.benchmark import VerilogEvalCase
from rechisel.llm_utils import ChiselCode, ModelMapping, Traces, read_prompt
from rechisel.verify import VerifyResult
from rechisel.config import MODELSEL, PROMPTSEL


@dataclass
class SyntaxReflCorrResult:
    sbt_reflection: str = ''
    iv_reflection: str = ''
    syntax_correction: str = ''

    def syntax_reflection(self):
        feedback = list()
        if self.sbt_reflection:
            feedback.append(
                "SBT Compilation Failed.\n"
                f"This is the feedback on how to correct the Scala code:\n"
                f"{self.sbt_reflection}\n"
            )
        if self.iv_reflection:
            feedback.append(
                "IV Compilation Failed.\n"
                f"This is the feedback on how to correct the Verilog code:\n"
                f"{self.iv_reflection}\n"
            )
        return "".join(feedback)


class SyntaxRefxCorrAgent:
    
    def __init__(
            self,
            testcase: VerilogEvalCase,
            code: ChiselCode,
            verify_result: VerifyResult,
    ):
        self._result = SyntaxReflCorrResult()
        self._code = code
        self._testcase = testcase
        self._verify_result = verify_result
    
    @property
    def result(self):
        return self._result
    
    @cached_property
    def sbt_reflection_user_input(self) -> str:
        return {
            'role': 'user',
            'content': (
                f"SPECIFICATION:\n```\n{self._testcase.specification}\n```\n\n"
                f"CHISEL CODE:\n```scala\n{self._code.raw_stripped}\n```\n\n"
                f"SBT ERROR INFO:\n```\n{self._verify_result.sbt_error}\n```\n"
            )
        }

    def sbt_reflection(
            self, traces: Traces | None = None
    ) -> bool:
        if self._verify_result.sbt_success:
            return False
        sysprompt = read_prompt(PROMPTSEL.sbt_reflection)
        messages = [{'role': 'system', 'content': sysprompt}]
        if traces:
            messages.extend(traces.get_traces())
        messages.append(self.sbt_reflection_user_input)
        sbt_reflection, _, _ = get_model_completion(
            messages, model=ModelMapping[MODELSEL.sbt_reflection]
        )
        self._result.sbt_reflection = sbt_reflection
        if traces:
            traces.add_trace(self.sbt_reflection_user_input)
            traces.add_trace({'role': 'assistant', 'content': sbt_reflection})
        return True
    
    @cached_property
    def iv_reflection_user_input(self) -> str:
        return {
            'role': 'user',
            'content': (
                f"SPECIFICATION:\n```\n{self._testcase.specification}\n```\n\n"
                f"CHISEL CODE:\n```scala\n{self._code.raw_stripped}\n```\n\n"
                # f"VERILOG CODE:\n```\n{self._verify_result.verilog_code}\n```\n\n"
                f"IV ERROR INFO:\n```\n{self._verify_result.iv_error}\n```\n"
            )
        }

    def iv_reflection(
            self, traces: Traces | None = None
    ) -> bool:
        if self._verify_result.iv_success:
            return False
        sysprompt = read_prompt(PROMPTSEL.iv_reflection)
        messages = [{'role': 'system', 'content': sysprompt}]
        if traces:
            messages.extend(traces.get_traces())
        messages.append(self.iv_reflection_user_input)
        iv_reflection, _, _ = get_model_completion(
            messages, model=ModelMapping[MODELSEL.iv_reflection]
        )
        self._result.iv_reflection = iv_reflection
        if traces:
            traces.add_trace(self.iv_reflection_user_input)
            traces.add_trace({'role': 'assistant', 'content': iv_reflection})
        return True
    
    @cached_property
    def syntax_correction_user_input(self) -> str:
        return {
            'role': 'user',
            'content': (
                f"CHISEL CODE:\n```scala\n{self._code.raw_stripped}\n```\n\n"
                f"FEEDBACK:\n```\n{self._result.syntax_reflection()}\n```\n"
            )
        }

    def syntax_correction(
            self,
            traces: Traces | None = None
    ) -> bool:
        sysprompt = read_prompt(PROMPTSEL.syntax_correction)
        messages = [
            {'role': 'system', 'content': sysprompt},
            {'role': 'user', 'content': (
                f"SPECIFICATION:\n```\n{self._testcase.specification}\n```\n\n"
            )}
        ]
        if traces:
            messages.extend(traces.get_traces())
        messages.append(self.syntax_correction_user_input)
        syntax_correction, _, _ = get_model_completion(
            messages, model=ModelMapping[MODELSEL.syntax_correction]
        )
        self._result.syntax_correction = syntax_correction
        if traces:
            traces.add_trace(self.syntax_correction_user_input)
            traces.add_trace({'role': 'assistant', 'content': syntax_correction})
        return True
    