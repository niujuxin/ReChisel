from rechisel.benchmark import VerilogEvalCase
from rechisel.functionality_corr import FunctionalityReflCorrAgent, FunctionalityReflCorrResult
from rechisel.llm_utils import ChiselCode, Traces
from rechisel.syntax_corr import SyntaxReflCorrResult, SyntaxRefxCorrAgent
from rechisel.verify import Verifier, VerifyResult


def verification(
    benchcase: VerilogEvalCase,
    chisel_code: ChiselCode,
    verifier: Verifier,
) -> VerifyResult:
    ok = (
        verifier.prepare(chisel_code, benchcase) and
        verifier.compile() and
        verifier.iv() and
        verifier.vvp() and
        verifier.functionality()
    )
    verify_result: VerifyResult = verifier.result
    return verify_result


def syntax_correction(
    benchcase: VerilogEvalCase,
    chisel_code: ChiselCode,
    verify_result: VerifyResult,
    sbt_reflection_traces: Traces | None = None,
    iv_reflection_traces: Traces | None = None,
    syntax_correction_traces: Traces | None = None,
) -> SyntaxReflCorrResult:
    syntax_agent = SyntaxRefxCorrAgent(
        testcase=benchcase,
        code=chisel_code,
        verify_result=verify_result,
    )
    ok = (
        (
            syntax_agent.sbt_reflection(traces=sbt_reflection_traces) or \
            syntax_agent.iv_reflection(traces=iv_reflection_traces)
        ) and
        syntax_agent.syntax_correction(traces=syntax_correction_traces)
    )
    correction_result: SyntaxReflCorrResult = syntax_agent.result
    return correction_result


def functinoality_correction(
    benchcase: VerilogEvalCase,
    chisel_code: ChiselCode,
    verify_result: VerifyResult,
    chisel_reflection_traces: Traces | None = None,
    correction_traces: Traces | None = None,
) -> FunctionalityReflCorrResult:
    functionality_agent = FunctionalityReflCorrAgent(
        testcase=benchcase,
        code=chisel_code,
        verify_result=verify_result,
    )
    ok = (
        functionality_agent.chisel_reflection(traces=chisel_reflection_traces) and
        functionality_agent.functionality_correction(traces=correction_traces)
    )
    correction_result: FunctionalityReflCorrResult = functionality_agent.result
    return correction_result