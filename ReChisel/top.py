
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage

from ReChisel.testcase import Testcase
from ReChisel.llms import get_llm_client, llm_call_with_retry
from ReChisel.chisel_code import ChiselCode
from ReChisel.verifier import Verifier, VerifierWorkingSpace, VerifyResult


def initial_chisel_generation(
        testcase: Testcase, top_module_name: str, *,
        system_prompt: str, model: str
) -> ChiselCode:
    messages = [
        SystemMessage(system_prompt),
        HumanMessage(testcase.specification)
    ]
    client = get_llm_client(model)
    response = llm_call_with_retry(client, messages)
    code = ChiselCode(response.content, top_module_name)
    return code


def verify(
        code: ChiselCode, bmcase: Testcase, output_dir: Path, bm_type: str, 
        *, verbose: bool = False
) -> tuple[bool, 'VerifyResult']:

    # Create working space for the verifier
    working_space = VerifierWorkingSpace(output_dir / 'chisel', output_dir / 'iv')
    # Initialize the verifier
    verifier = Verifier(working_space, verbose=verbose)

    # Prepare the verification process
    _ = (
        verifier.prepare(code, bmcase) and
        verifier.chisel_compile_to_verilog() and
        verifier.verilog_compile() and
        verifier.run_verilog_sim() and
        verifier.functionality_eval(bm_type=bm_type)
    )
    return verifier.result


def collect_feedback_prepare_reflection(
        testcase: Testcase,
        verify_result: VerifyResult,
        chisel_code: ChiselCode
):
    
    def prepare_sbt_error():
        pass

    def prepare_iv_error():
        pass
