from dataclasses import dataclass
import os
import re
from typing import Literal
import uuid
import shutil

from rechisel.benchmark import VerilogEvalCase
from rechisel.config import PATHS, RELPATHS
from rechisel.llm_utils import ChiselCode
from rechisel.utils import subprocess_run


@dataclass
class VerifyResult:
    # compile()
    sbt_success: bool = False
    sbt_error: str = ''
    verilog_code: str = ''
    # iv()
    iv_success: bool = False
    iv_error: str = ''
    # vvp()
    vvp_success: bool = False
    vvp_output: str = ''
    # func_verilog_eval()
    functionality_correct: bool = False

    @property
    def syntax_correct(self):
        return self.sbt_success and self.iv_success


class VerifyWorkingSpace:
    def __init__(self):
        self._key = uuid.uuid4().hex

        self._chisel_path = os.path.join(PATHS.working_space, self._key)
        self._iv_path = os.path.join(self._chisel_path, RELPATHS.iv)

        # Copy all files in chisel_project_template to chisel_path
        os.makedirs(self._chisel_path, exist_ok=True)
        shutil.copytree(PATHS.chisel_project_template, self._chisel_path, dirs_exist_ok=True)
        os.makedirs(self._iv_path, exist_ok=True)
    
    @property
    def key(self):
        return self._key
    
    @property
    def chisel_path(self):
        return self._chisel_path
    
    @property
    def iv_path(self):
        return self._iv_path
    
    def __del__(self):
        pass
        # shutil.rmtree(self._chisel_path, ignore_errors=True)


def sbtout_clean(sbtout: str):
    # Remove the empty lines and all lines begin with `\s*| =>`
    sbtout = re.sub(r'^\s*\| =>.*\n', '', sbtout, flags=re.MULTILINE)
    sbtout = "\n".join(
        [line for line in sbtout.split('\n') if line.strip()]
    )
    # Remove all [info] lines and [warn] lines
    sbtout = re.sub(r'^\s*\[info\].*\n', '', sbtout, flags=re.MULTILINE)
    sbtout = re.sub(r'^\s*\[warn\].*\n', '', sbtout, flags=re.MULTILINE)
    return sbtout


class Verifier:
    def __init__(
            self, 
            working_space: VerifyWorkingSpace,
            benchmark: Literal['autochip', 'verilog-eval']
    ):
        self._working_space = working_space
        self._benchmark = benchmark

    @property
    def result(self):
        return self._result

    def prepare(
            self, 
            code: ChiselCode,
            testcase: VerilogEvalCase
    ):
        self._result = VerifyResult()
        with open(os.path.join(
            self._working_space.chisel_path, RELPATHS.chisel_main_path
        ), 'w') as f:
            f.write(code.decorated)
        testcase.prepare_iv(self._working_space.iv_path)
        return True
    
    def compile(self):
        is_success, _, sbt_out, _ = subprocess_run(
            ['sbt', 'run'],
            cwd=self._working_space.chisel_path,
        )
        if is_success:
            self._result.sbt_success = True
            # Extract Verilog code.
            fpath = os.path.join(
                self._working_space.chisel_path, 
                'generated'
            )
            vf = [
                f for f in os.listdir(fpath) 
                if f.endswith('.v') or f.endswith('.sv')
            ][0] # There must be only one verilog file
            with open(os.path.join(fpath, vf), 'r') as f:
                self._result.verilog_code = f.read()
        else:
            self._result.sbt_error = sbtout_clean(sbt_out)

        return is_success

    def iv(self, output_fname: str = 'a.out', top_fname: str = 'top.v'):
        # Write the verilog code to a file
        with open(os.path.join(
            self._working_space.iv_path, top_fname
        ), 'w') as f:
            f.write(self._result.verilog_code)
        # Find all file with .sv extension or .v extension in iv_path
        files = [
            f for f in os.listdir(self._working_space.iv_path)
            if f.endswith('.sv') or f.endswith('.v')
        ]
        command = ['iverilog', '-g2012', '-o', output_fname, *files]
        is_success, _, iv_out, iv_err = subprocess_run(
            command, cwd=self._working_space.iv_path
        )
        
        if is_success:
            self._result.iv_success = True
        else:
            self._result.iv_error = "Error: Cannot run Icarus Verilog.\n\n"
            if iv_out:
                self._result.iv_error += f"Console STD Output: \n{iv_out}\n"
            if iv_err:
                self._result.iv_error += f"Console ERR Output: \n{iv_err}\n"
        
        return is_success

    def vvp(self, output_fname: str = 'a.out'):
        is_success, _, vvp_out, vvp_err = subprocess_run(
            ['vvp', output_fname], cwd=self._working_space.iv_path
        )
        if is_success:
            self._result.vvp_success = True
            self._result.vvp_output = vvp_out
        else:
            self._result.vvp_output = (
                f"Error: Cannot run VVP.\n\n"
                f"Console STD Output: {vvp_out}\n\n"
                f"Console ERR Output: {vvp_err}"
            )
        
        return is_success

    def func_verilog_eval(self):
        mismatch_pattern = re.compile(r'Mismatches: (\d+) in (\d+) samples')
        m = mismatch_pattern.search(self._result.vvp_output)
        if m:
            mismatches = int(m.group(1))
            if mismatches == 0:
                self._result.functionality_correct = True
            return mismatches == 0
        else:
            return False

    def func_autochip(self):
        is_correct = "All tests passed!" in self._result.vvp_output
        self._result.functionality_correct = is_correct
        return is_correct

    def functionality(self):
        if self._benchmark == 'autochip':
            return self.func_autochip()
        elif self._benchmark == 'verilog-eval':
            return self.func_verilog_eval()
        else:
            return False
        