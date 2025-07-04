from typing import Optional
from ReChisel.chisel_code import ChiselCode
from ReChisel.llms import get_llm_client, llm_call_with_retry
from ReChisel.testcase import Testcase


from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage

from ReChisel.verifier import VerifyResult, collect_verify_feedback


class Generator:
    def __init__(
            self, *, 
            init_gen_system_prompt: str, 
            init_gen_model: str,
            syntax_correction_system_prompt: str,
            functionality_correction_system_prompt: str,
            correction_model: str,
            verbose: bool = False
    ):
        self._init_gen_system_prompt = init_gen_system_prompt
        self._init_gen_model = init_gen_model

        self._syntax_correction_system_prompt = syntax_correction_system_prompt
        self._functionality_correction_system_prompt = functionality_correction_system_prompt
        self._correction_model = correction_model

        self._verbose = verbose

    def _log(self, message: str):
        if self._verbose:
            # TODO: Use `logging` module instead of print
            print(f"[GENERATOR] {message}")

    def testcase_prepare(self, testcase: Testcase, top_module_name: str):
        self._log("Preparing testcase for code generation.")
        self._testcase = testcase
        self._top_module_name = top_module_name
        self._log("Testcase:" + str(testcase))
        self._log("Top module name: " + top_module_name)

    def code_extract(self, response: BaseMessage) -> ChiselCode:
        if not isinstance(response, BaseMessage):
            raise TypeError("Expected response to be an instance of BaseMessage.")
        code = ChiselCode(response.content, self._top_module_name)
        self._log("Chisel code extracted.")
        return code

    def initial_chisel_generation(self) -> AIMessage:
        self._log("Preparing messages for initial Chisel code generation.")
        messages = [
            SystemMessage(self._init_gen_system_prompt),
            HumanMessage(self._testcase.specification)
        ]
        self._log(f"Calling LLM for initial Chisel code generation with model {self._init_gen_model}.")
        client = get_llm_client(self._init_gen_model)
        response = llm_call_with_retry(client, messages)
        self._log("Initial Chisel code generation response received.")
        return response

    def _correction_system_prompt(self, verify_result: VerifyResult) -> SystemMessage:
        if not verify_result.chisel_compile_to_verilog_success:
            self._log("Adopting syntax correction system prompt for Chisel compilation failure.")
            return SystemMessage(self._syntax_correction_system_prompt)
        elif not verify_result.verilog_compile_success:
            self._log("Adopting syntax correction system prompt for Verilog compilation failure.")
            return SystemMessage(self._syntax_correction_system_prompt)
        elif not verify_result.functionality_correct:
            self._log("Adopting functionality correction system prompt.")
            return SystemMessage(self._functionality_correction_system_prompt)
        else:
            raise ValueError("Unexpected verification result: functionality_correct is True, the code should not reach here.")

    def correction_generation(
            self, 
            reviewer_response: AIMessage, 
            verify_result: VerifyResult, 
            chisel_code: ChiselCode,
            in_context_history: Optional[HumanMessage] = None
    ) -> AIMessage:
        
        self._log("Preparing messages for correction generation.")
        # Basic messages for correction generation
        messages = [
            self._correction_system_prompt(verify_result),
            HumanMessage(self._testcase.specification),
        ]
        # If in-context history is provided, include it in the messages
        if in_context_history is not None:
            messages.append(in_context_history)
        # This attempt.
        messages.extend([
            collect_verify_feedback(verify_result, chisel_code),
            HumanMessage(reviewer_response.content)
        ])
        
        self._log(f"Calling LLM for correction generation with model {self._correction_model}.")
        client = get_llm_client(self._correction_model)
        response = llm_call_with_retry(client, messages)
        self._log("Correction generation response received.")
        return response
