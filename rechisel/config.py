import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class Paths:
    working_space: str = 'benchmark_working_space'
    chisel_project_template: str = 'benchmark_working_space/chisel_project_template'
    prompt_pool: str = 'prompts/'
    verilog_eval_benchmark: str = 'benchmarks/dataset_spec-to-rtl'
    autochip_reference: str = 'benchmarks/autochip_ref'
    autochip_prompt: str = 'benchmarks/autochip_prompt'
    autochip_exclusive: str = 'autochip_exclusive.txt'

    def adjust(self, base: str):
        keys = self.__annotations__.keys()
        for k in keys:
            p = os.path.abspath(os.path.join(base, getattr(self, k)))
            setattr(self, k, p)


PATHS = Paths()


@dataclass
class RelPaths:
    verilog_eval_src: str = ''
    verilog_eval_prob_list: str = 'problems.txt'
    autochip_prompt: str = 'hdlbits_prompts'
    autochip_testbench: str = 'hdlbits_testbenches'
    iv: str = 'iv'
    chisel_main_path: str = 'src/main/scala/Main.scala'


RELPATHS = RelPaths()


SelModelTy = Literal['gpt4omini', 'gpt4o', 'gpt35turbo', 'gpt4turbo']

@dataclass
class ModelSelection:
    init_gen: SelModelTy = 'gpt4omini'
    sbt_reflection: SelModelTy = 'gpt4omini'
    iv_reflection: SelModelTy = 'gpt4omini'
    syntax_correction: SelModelTy = 'gpt4omini'
    functionality_reflection_chisel: SelModelTy = 'gpt4omini'
    functionality_correction_verilog: SelModelTy = 'gpt4omini'
    functionality_correction: SelModelTy = 'gpt4omini'

    def apply_all(self, model: SelModelTy):
        keys = self.__annotations__.keys()
        for k in keys:
            setattr(self, k, model)

MODELSEL = ModelSelection()


@dataclass
class PromptSelection:
    init_gen: str = 'chisel-generation'
    sbt_reflection: str = 'syntax-sbt-reflection'
    iv_reflection: str = 'syntax-iv-reflection'
    syntax_correction: str = 'syntax-correction'
    functionality_reflection_uni = 'functionality-reflection'
    functionality_correction: str = 'functionality-correction'


PROMPTSEL = PromptSelection()
