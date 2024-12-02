import re
from typing import Literal
from rechisel.config import PATHS, RELPATHS


import os
import glob
from functools import cached_property, lru_cache


def read_benchmark_list(
        benchmark_dir: str, problem_list_key: str
) -> list[str]:
    d = os.path.join(benchmark_dir, problem_list_key)
    with open(d, 'r') as f:
        return [line.strip() for line in f.readlines() if line.strip()]


class VerilogEvalCase:
    def __init__(
            self, 
            prob_id: str, 
            benchmark_dir: str = PATHS.verilog_eval_benchmark
    ):
        self._prob_id = prob_id
        self._benchmark_dir = benchmark_dir
    
    @cached_property
    def specification(self):
        with open(os.path.join(
            self._benchmark_dir, RELPATHS.verilog_eval_src, f'{self._prob_id}_prompt.txt'
        ), 'r') as f:
            return f.read()
    
    def prepare_iv(
            self, cwd: str,
            *,
            reference_path: str = 'ref.sv',
            test_path: str = 'test.sv'
    ) -> bool:
        # This method moves reference and test files to the working directory
        # Copy `{prob_id}_ref.sv` to `cwd/ref.sv`
        with open(os.path.join(
            self._benchmark_dir, RELPATHS.verilog_eval_src, f'{self._prob_id}_ref.sv'
        ), 'r') as f:
            with open(os.path.join(cwd, reference_path), 'w') as f2:
                f2.write(f.read())
        # Copy `{prob_id}_test.sv` to `cwd/test.sv`
        with open(os.path.join(
            self._benchmark_dir, RELPATHS.verilog_eval_src, f'{self._prob_id}_test.sv'
        ), 'r') as f:
            with open(os.path.join(cwd, test_path), 'w') as f2:
                f2.write(f.read())
        return True


class VerilogEvalBenchmark:

    def __init__(self, problem_list_key: str | None = None):
        self._problem_list_key = problem_list_key or RELPATHS.verilog_eval_prob_list
        self._benchmark_dir = PATHS.verilog_eval_benchmark

    @cached_property
    def problem_keys(self):
        with open(os.path.join(
            self._benchmark_dir, self._problem_list_key
        ), 'r') as f:
            keys = set(line.strip() for line in f.readlines() if line.strip())
        
        return list(keys)

    @lru_cache
    def get_case(self, prob_id: str) -> VerilogEvalCase:
        return VerilogEvalCase(prob_id, self._benchmark_dir)
    


class AutoChipCase:
    def __init__(
            self,
            prob_id: str,
            reference_dir: str = PATHS.autochip_reference,
            prompt_dir: str = PATHS.autochip_prompt
    ):
        self._prob_id = prob_id
        self._prompt_dir = prompt_dir
        self._reference_dir = reference_dir
    
    @cached_property
    def specification_autochip(self):
        with open(os.path.join(
            self._prompt_dir, f'{self._prob_id}.txt'
        ), 'r') as f:
            spec = f.read()
        return spec

    @cached_property
    def specification(self):

        return self.specification_autochip

        if False:
            spec = self.specification_autochip

            pattern = re.compile(
                r'module\s+(\w+)\s*\((.*)\);(.*)endmodule', re.DOTALL
            )
            match = pattern.search(spec)
            if match is None:
                raise ValueError(f'Cannot find module definition for case {self._prob_id}')
            
            top_module_name = match.group(1)

            port_list = match.group(2)
            port_list = [p.strip() for p in port_list.split('\n')]
            port_list = "\n".join([f"  {p}" for p in port_list if p.strip() != ''])

            prompt_others = re.sub(pattern, '', spec)
            prompt_others = re.sub(r'//\s*', '', prompt_others)
            prompt_others = re.sub(r'\n+', '\n', prompt_others)
            prompt_others.strip()

            return (
                f"I would like you to implement a module named `{top_module_name}` with the following interface. \n"
                f"All input and output ports are one bit wide unless otherwise specified.\n\n"
                f"Module Name: `{top_module_name}`\n"
                f"Ports:\n"
                f"{port_list}\n\n"
                f"{prompt_others}"
            )
    
    @cached_property
    def reference(self):
        with open(os.path.join(
            self._reference_dir, f'{self._prob_id}.v'
        ), 'r') as f:
            return f.read()
    
    def prepare_iv(
            self, cwd: str,
            *,
            test_path: str = 'test.v'
    ) -> bool:
        # This method moves test files to the working directory
        # Copy `{prob_id}_0_tb.v` to `cwd/test.v`
        with open(os.path.join(
            self._reference_dir, f'{self._prob_id}.v'
        ), 'r') as f:
            with open(os.path.join(cwd, test_path), 'w') as f2:
                f2.write(f.read())
        return True


class AutoChipBenchmark:
    def __init__(self):
        self._reference_dir = PATHS.autochip_reference
        self._prompt_dir = PATHS.autochip_prompt

    @cached_property
    def problem_keys(self):
        prompt_files = glob.glob(os.path.join(
            self._prompt_dir, '*.txt'
        ))
        keys = set(os.path.basename(f)[: -4] for f in prompt_files)

        try:
            with open(PATHS.autochip_exclusive, 'r') as f:
                exclusive_keys = set(line.strip() for line in f.readlines() if line.strip())
        except FileNotFoundError:
            exclusive_keys = set()
            
        for key in exclusive_keys:
            if '*' in key:
                keys = {k for k in keys if not re.match(key, k)}
            else:
                keys.discard(key)

        return list(keys)

    @lru_cache
    def get_case(self, prob_id: str) -> AutoChipCase:
        return AutoChipCase(prob_id, self._reference_dir, self._prompt_dir)
    
