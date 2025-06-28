from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal
import shutil

from ReChisel.testcase import Testcase
from ReChisel.chisel_code import ChiselCode
from ReChisel.utils import run_command


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
    # func_verilog_eval() or func_autochip()
    functionality_correct: bool = False

    @property
    def syntax_correct(self):
        return self.sbt_success and self.iv_success


class VerifierWorkingSpace:
    def __init__(self, chisel_dir: str | Path, iv_dir: str | Path, *, sbt_build_path: str | Path = 'build.sbt'):
        self.chisel_dir = Path(chisel_dir)
        self.iv_dir = Path(iv_dir)
        self.sbt_build_path = Path(sbt_build_path)
        
        # Create directories if they don't exist
        self.chisel_dir.mkdir(parents=True, exist_ok=True)
        self.iv_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy sbt build file to chisel dir
        self._setup_sbt_build()
    
    def _setup_sbt_build(self) -> None:
        """Copy sbt build file to chisel directory"""
        target_sbt = self.chisel_dir / "build.sbt"
        if self.sbt_build_path.exists() and not target_sbt.exists():
            shutil.copy2(self.sbt_build_path, target_sbt)


class Verifier:
    def __init__(
            self, 
            working_space: VerifierWorkingSpace,
            benchmark: Literal['autochip', 'verilog-eval']
    ):
        self._working_space = working_space
        self._benchmark = benchmark

    @property
    def result(self):
        return self._result

    def prepare(self, code: ChiselCode, testcase: Testcase):
        self._result = VerifyResult()
        
        # Build Chisel's compiler env.
        chisel_code_path = self._working_space.chisel_dir / "src/main/scala/Main.scala"
        chisel_code_path.parent.mkdir(parents=True, exist_ok=True)
        chisel_code_path.touch()
        chisel_code_path.write_text(code.decorated, encoding='utf-8')
        
        # Move the reference code and testbench code to IV's working directory. 
        self._working_space.iv_dir.mkdir(parents=True, exist_ok=True)
        files_to_write = [
            (testcase.reference_code, f'{testcase.prob_id}_ref.sv'),
            (testcase.testbench_code, f'{testcase.prob_id}_tb.sv')
        ]
        for content, filename in files_to_write:
            if content:
                target_file = self._working_space.iv_dir / filename
                target_file.write_text(content, encoding='utf-8')
        
        return True
    
    @staticmethod
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

    def compile(self):
        sbt_returncode, sbt_out, _ = run_command(
            'sbt run', workingdir=self._working_space.chisel_dir
        )
        if sbt_returncode != 0:
            self._result.sbt_error = self.sbtout_clean(sbt_out)
            return False
        
        self._result.sbt_success = True

        # Extract Verilog code
        generated_dir = self._working_space.chisel_dir / "generated"
        verilog_files = [
            f for f in generated_dir.iterdir() if f.suffix in {'.v', '.sv'}
        ]

        if not verilog_files:
            raise FileNotFoundError("No Verilog files found in generated directory")
        if len(verilog_files) > 1:
            raise RuntimeError(f"Multiple Verilog files found: {[f.name for f in verilog_files]}")
        
        with open(verilog_files[0], 'r') as f:
            self._result.verilog_code = f.read()

        return True

    def iv(self, output_fname: str = 'a.out', top_fname: str = 'top.v'):
        # Write the verilog code to a file
        verilog_file = self._working_space.iv_dir / top_fname
        verilog_file.write_text(self._result.verilog_code)

        # Find all files with .sv or .v extension in iv_dir
        verilog_files = [
            f.relative_to(self._working_space.iv_dir)
            for f in self._working_space.iv_dir.iterdir()
            if f.suffix in {'.sv', '.v'}
        ]
        
        command = ['iverilog', '-g2012', '-o', output_fname, *verilog_files]
        returncode, iv_out, iv_err = run_command(
            command, workingdir=self._working_space.iv_dir
        )
        
        if returncode == 0:
            self._result.iv_success = True
            return True
        
        self._result.iv_error = (
            "Error: Failed to run Icarus Verilog.\n\n",
            f"# STDOUT:\n\n```\n{iv_out}\n```\n\n",
            f"# STDERR:\n\n```\n{iv_err}\n```"
        )
        return False

    def vvp(self, output_fname: str = 'a.out'):
        returncode, vvp_out, vvp_err = run_command(
            ['vvp', output_fname], workingdir=self._working_space.iv_dir
        )
        
        if returncode == 0:
            self._result.vvp_success = True
            self._result.vvp_output = vvp_out
            return True
        
        self._result.vvp_output = (
            "Error: Failed to run VVP.\n\n",
            f"# STDOUT:\n\n```\n{vvp_out}\n```\n\n",
            f"# STDERR:\n\n```\n{vvp_err}\n```"
        )
        return False

    def _func_verilog_eval(self):
        mismatch_pattern = re.compile(r'Mismatches: (\d+) in (\d+) samples')
        match = mismatch_pattern.search(self._result.vvp_output)
        
        if not match:
            return False
        
        mismatches = int(match.group(1))
        is_correct = mismatches == 0
        self._result.functionality_correct = is_correct
        return is_correct

    def _func_autochip(self):
        is_correct = "All tests passed!" in self._result.vvp_output
        self._result.functionality_correct = is_correct
        return is_correct

    def functionality(self):
        if self._benchmark == 'autochip':
            return self._func_autochip()
        elif self._benchmark == 'verilog-eval':
            return self._func_verilog_eval()
        else:
            return False
