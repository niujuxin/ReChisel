


from dataclasses import dataclass
from functools import cached_property

from rechisel.benchmark import VerilogEvalCase
from rechisel.config import MODELSEL, PROMPTSEL
from rechisel.llm_utils import ChiselCode, ModelMapping, Traces, read_prompt
from rechisel.llm_client import get_model_completion
from rechisel.verify import VerifyResult


@dataclass
class FunctionalityReflCorrResult:
    functionality_reflection_chisel: str = ''
    functionality_correction_verilog: str = ''
    functionality_correction: str = ''


class FunctionalityReflCorrAgent:

    def __init__(
            self,
            testcase: VerilogEvalCase,
            code: ChiselCode,
            verify_result: VerifyResult,
    ):
        self._result = FunctionalityReflCorrResult()
        self._code = code
        self._testcase = testcase
        self._verify_result = verify_result

    @property
    def result(self):
        return self._result
    
    @cached_property
    def user_input_chisel(self) -> str:
        return {
            'role': 'user',
            'content': (
                f"SPECIFICATION:\n```\n{self._testcase.specification}\n```\n\n"
                f"CHISEL CODE:\n```scala\n{self._code.raw_stripped}\n```\n\n"
                f"ERROR INFO:\n```\n{self._verify_result.vvp_output}\n```\n"
            )
        }
    
    def chisel_reflection(self, traces: Traces | None = None) -> bool:
        sysprompt = read_prompt(PROMPTSEL.functionality_reflection_uni)
        sysprompt.replace(r'{{LANG}}', 'Chisel')
        messages = [{'role': 'system', 'content': sysprompt}]
        if traces:
            messages.extend(traces.get_traces())
        messages.append(self.user_input_chisel)
        chisel_reflection, _, _ = get_model_completion(
            messages, 
            model=ModelMapping[MODELSEL.functionality_reflection_chisel]
        )
        self._result.functionality_reflection_chisel = chisel_reflection
        if traces:
            traces.add_trace(self.user_input_chisel)
            traces.add_trace({'role': 'assistant', 'content': chisel_reflection})
        return True
    
    @cached_property
    def functionality_correction_user_input(self) -> str:
        return {
            'role': 'user',
            'content': (
                f"SPECIFICATION:\n```\n{self._testcase.specification}\n```\n\n"
                f"CHISEL CODE:\n```scala\n{self._code.raw_stripped}\n```\n\n"
                f"VVP OUTPUT:\n```\n{self._verify_result.vvp_output}\n```\n"
            )
        }
    
    def functionality_correction(
            self, traces: Traces | None = None
    ) -> bool:
        sysprompt = read_prompt(PROMPTSEL.functionality_correction)
        messages = [{'role': 'system', 'content': sysprompt}]
        if traces:
            messages.extend(traces.get_traces())
        messages.append(self.functionality_correction_user_input)
        functionality_correction, _, _ = get_model_completion(
            messages, 
            model=ModelMapping[MODELSEL.functionality_correction]
        )
        self._result.functionality_correction = functionality_correction
        if traces:
            traces.add_trace(self.functionality_correction_user_input)
            traces.add_trace({'role': 'assistant', 'content': functionality_correction})
        return True
    