
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage

from ReChisel.testcase import Testcase
from ReChisel.llms import get_llm_client, llm_call_with_retry
from ReChisel.chisel_code import ChiselCode


class ModelSelection:
    chisel_gen = 'gpt-4o-mini'
    sbt_reflection = 'gpt-4o-mini'
    iv_reflection = 'gpt-4o-mini'
    syntax_correction = 'gpt-4o-mini'
    functionality_reflection_chisel = 'gpt-4o-mini'
    functionality_correction_verilog = 'gpt-4o-mini'
    functionality_correction = 'gpt-4o-mini'


class Prompts:
    chisel_generation = Path('prompts/chisel_generation.txt').read_text(encoding='utf-8')
    syntax_iv_reflection = Path('prompts/syntax_iv_reflection.txt').read_text(encoding='utf-8')
    syntax_sbt_reflection = Path('prompts/syntax_sbt_reflection.txt').read_text(encoding='utf-8')
    syntax_correction = Path('prompts/syntax_correction.txt').read_text(encoding='utf-8')
    functionality_reflection = Path('prompts/functionality_reflection.txt').read_text(encoding='utf-8')
    functionality_correction = Path('prompts/functionality_correction.txt').read_text(encoding='utf-8')


def initial_chisel_generation(bmcase: Testcase, top_module_name: str) -> ChiselCode:
    messages = [
        SystemMessage(Prompts.chisel_generation),
        HumanMessage(bmcase.specification)
    ]
    client = get_llm_client(ModelSelection.chisel_gen)
    response = llm_call_with_retry(client, messages)
    code = ChiselCode(response.content, top_module_name)
    return code
