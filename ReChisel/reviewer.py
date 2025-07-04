
from langchain_core.messages import SystemMessage, AIMessage

from ReChisel.chisel_code import ChiselCode
from ReChisel.llms import get_llm_client, llm_call_with_retry
from ReChisel.testcase import Testcase
from ReChisel.verifier import VerifyResult, collect_verify_feedback



class Reviewer:
    def __init__(
            self, *,
            sbt_system_prompt: str,
            iv_system_prompt: str,
            functionality_system_prompt: str,
            model: str,
            verbose: bool = False,
    ):
        self._sbt_system_prompt = sbt_system_prompt
        self._iv_system_prompt = iv_system_prompt
        self._functionality_system_prompt = functionality_system_prompt
        self._model = model
        self._verbose = verbose

    def _log(self, message: str):
        if self._verbose:
            # TODO: Use `logging` module instead of print
            print(f"[REVIEWER] {message}")

    def _reflection_system_prompt(self, verify_result: VerifyResult) -> SystemMessage:
        if not verify_result.chisel_compile_to_verilog_success:
            self._log("Adopting SBT reflection system prompt.")
            return SystemMessage(self._sbt_system_prompt)
        elif not verify_result.verilog_compile_success:
            self._log("Adopting IV reflection system prompt.")
            return SystemMessage(self._iv_system_prompt)
        elif not verify_result.functionality_correct:
            self._log("Adopting functionality reflection system prompt.")
            return SystemMessage(self._functionality_system_prompt)
        else:
            raise ValueError("Unexpected verification result: functionality_correct is True, the code should not reach here.")
        
    def review(self, testcase: Testcase, verify_result: VerifyResult, chisel_code: ChiselCode) -> AIMessage:
        self._log("Preparing messages for reflection.")
        messages = [
            self._reflection_system_prompt(verify_result),
            collect_verify_feedback(testcase, verify_result, chisel_code)
        ]
        self._log(f"Calling LLM for reflection with model {self._model}.")
        client = get_llm_client(self._model)
        response = llm_call_with_retry(client, messages)
        self._log("Reflection response received.")
        return response
    
    def __call__(self, testcase: Testcase, verify_result: VerifyResult, chisel_code: ChiselCode) -> AIMessage:
        return self.review(testcase, verify_result, chisel_code)
