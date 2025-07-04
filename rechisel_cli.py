
import argparse
from pathlib import Path
from pprint import pprint
import json

from langchain_core.messages import AIMessage

from ReChisel.chisel_code import ChiselCode
from ReChisel.generator import Generator
from ReChisel.reviewer import Reviewer
from ReChisel.testcase import Testcase
from ReChisel.tracing import Tracing, in_context_attempt_history_format
from ReChisel.verifier import VerifyResult, verify


args = argparse.ArgumentParser(description="ReChisel CLI")

args.add_argument('--verbose', action='store_true', help='Enable verbose output')
args.add_argument('-o', '--output', type=str, required=False, default='output/output.json', help='Output file for the results')
args.add_argument('-n', '--num-iterations', type=int, required=False, default=10, help='Maximum number of iterations for the generation and verification process')
# Testcase
args.add_argument('--prob-id', type=str, required=False, default='prob_0', help='Problem ID')
args.add_argument('--specification', type=str, required=True, help='Specification directory')
args.add_argument('--reference', type=str, required=False, default=None, help='Reference directory')
args.add_argument('--testbench', type=str, required=True, help='Testbench directory')
args.add_argument('--top-module-name', type=str, required=False, default='TopModule', help='Top module name')
args.add_argument('--bm-type', type=str, required=True, help='Benchmark type for verification')
# Generator
args.add_argument('--init-gen-system-prompt', type=str, required=False, default='prompts/chisel_generation.txt', help='Initial generation system prompt file')
args.add_argument('--init-gen-model', type=str, required=False, default='gpt-4o-mini', help='Initial generation model')
args.add_argument('--syntax-correction-system-prompt', type=str, required=False, default='prompts/syntax_correction.txt', help='Syntax correction system prompt file')
args.add_argument('--functionality-correction-system-prompt', type=str, required=False, default='prompts/functionality_correction.txt', help='Functionality correction system prompt file')
args.add_argument('--correction-model', type=str, required=False, default='gpt-4o-mini', help='Correction model')
# Reviewer
args.add_argument('--sbt-reflection-system-prompt', type=str, required=False, default='prompts/syntax_sbt_reflection.txt', help='SBT reflection system prompt file')
args.add_argument('--iv-reflection-system-prompt', type=str, required=False, default='prompts/syntax_iv_reflection.txt', help='IV reflection system prompt file')
args.add_argument('--functionality-reflection-system-prompt', type=str, required=False, default='prompts/functionality_reflection.txt', help='Functionality reflection system prompt file')
args.add_argument('--reviewer-model', type=str, required=False, default='gpt-4o-mini', help='Reviewer model')
# Verifier
args.add_argument('--verifier-working-dir', type=str, required=False, default='output/verification', help='Working directory for verification output')
# Tracing
args.add_argument('--use-in-context-history', action='store_true', help='Use in-context history for reflection')
args.add_argument('--use-llm-summary', action='store_true', help='Use LLM summary for tracing')
args.add_argument('--llm-summary-system-prompt', type=str, required=False, default='prompts/attempt_summary.txt', help='LLM summary system prompt file')
args.add_argument('--llm-summary-model', type=str, required=False, default='gpt-4o-mini', help='LLM model for summary generation')
args.add_argument('--max-history-length', type=int, required=False, default=5, help='Maximum length of history to keep in tracing')

args = args.parse_args()

pprint(vars(args))

bmcase = Testcase(
    prob_id=args.prob_id,
    specification_path=args.specification,
    reference_path=args.reference,
    testbench_path=args.testbench,
)

generator = Generator(
    init_gen_system_prompt=Path(args.init_gen_system_prompt).read_text(encoding='utf-8'),
    init_gen_model=args.init_gen_model,
    syntax_correction_system_prompt=Path(args.syntax_correction_system_prompt).read_text(encoding='utf-8'),
    functionality_correction_system_prompt=Path(args.functionality_correction_system_prompt).read_text(encoding='utf-8'),
    correction_model=args.correction_model,
    verbose=args.verbose
)
generator.testcase_prepare(bmcase, args.top_module_name)

reviewer = Reviewer(
    sbt_system_prompt=Path(args.sbt_reflection_system_prompt).read_text(encoding='utf-8'),
    iv_system_prompt=Path(args.iv_reflection_system_prompt).read_text(encoding='utf-8'),
    functionality_system_prompt=Path(args.functionality_reflection_system_prompt).read_text(encoding='utf-8'),
    model=args.reviewer_model,
    verbose=args.verbose
)

tracing = Tracing(
    bmcase,
    use_llm_summary=args.use_llm_summary,
    llm_summary_model=args.llm_summary_model,
    llm_summary_system_prompt=Path(args.llm_summary_system_prompt).read_text(encoding='utf-8'),
)


current_chisel_code: ChiselCode = None
current_verify_result: VerifyResult = None
current_reviewer_response: AIMessage = None
attempt_count = 0
is_passed = False


while True:
    print(f"==== Attempt {attempt_count + 1} ====")
    if current_reviewer_response is None:
        print("Generating initial Chisel code...")
        generation_response = generator.initial_chisel_generation()
    else:
        print("Generating correction for the current Chisel code...")
        if args.use_in_context_history:
            ictx_history = in_context_attempt_history_format(tracing, k=args.max_history_length)
        generation_response = generator.correction_generation(
            current_reviewer_response,
            current_verify_result,
            current_chisel_code,
            in_context_history=ictx_history if args.use_in_context_history else None
        )
    current_chisel_code = generator.code_extract(generation_response)

    print("Verifying the current Chisel code...")
    current_verify_result = verify(
        current_chisel_code,
        bmcase,
        output_dir=Path(args.verifier_working_dir),
        bm_type=args.bm_type,
        verbose=args.verbose
    )

    if current_verify_result.functionality_correct:
        print(f"Verification passed after {attempt_count + 1} attempts, stopping the process.")
        is_passed = True
        break
    else:
        print(f"Verification failed at attempt {attempt_count + 1}.")

    print(f"Reflecting on the verification result and Chisel code...")
    current_reviewer_response = reviewer(bmcase, current_verify_result, current_chisel_code)
        
    print("Adding attempt to tracing...")
    tracing.add_attempt(
        current_chisel_code, 
        current_verify_result, 
        current_reviewer_response
    )

    attempt_count += 1
    print(f"Attempt {attempt_count + 1} completed.\n")
    if attempt_count >= args.num_iterations:
        print("Maximum attempts reached, stopping the process.")
        break


# Save the result

output_path = Path(args.output)
output_path.parent.mkdir(parents=True, exist_ok=True)

rlt_dict = {
    'prompts': {
        'init_gen_system_prompt': args.init_gen_system_prompt,
        'syntax_correction_system_prompt': args.syntax_correction_system_prompt,
        'functionality_correction_system_prompt': args.functionality_correction_system_prompt,
        'sbt_reflection_system_prompt': args.sbt_reflection_system_prompt,
        'iv_reflection_system_prompt': args.iv_reflection_system_prompt,
        'functionality_reflection_system_prompt': args.functionality_reflection_system_prompt,
        'llm_summary_system_prompt': args.llm_summary_system_prompt
    },
    'llm_models': {
        'init_gen_model': args.init_gen_model,
        'correction_model': args.correction_model,
        'reviewer_model': args.reviewer_model,
        'llm_summary_model': args.llm_summary_model
    },
    'config': {
        'use_in_context_history': args.use_in_context_history,
        'use_llm_summary': args.use_llm_summary,
        'max_history_length': args.max_history_length,
        'num_iterations': args.num_iterations,
        'bm_type': args.bm_type,
        'verifier_working_dir': args.verifier_working_dir
    },
    'testcase': bmcase.to_dict(),
    'attempts': [
        attempt.to_dict() for attempt in tracing.attempts
    ],
    'is_passed': is_passed,
    'final_chisel_code': current_chisel_code.raw_stripped if current_chisel_code else None,
    'final_verify_result': current_verify_result.__dict__() if current_verify_result else None
}

with output_path.open('w', encoding='utf-8') as f:
    json.dump(rlt_dict, f, indent=2, ensure_ascii=False)

print(f"Results saved to {output_path}")
