from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal
import shutil

from ReChisel.testcase import Testcase
from ReChisel.chisel_code import ChiselCode
from ReChisel.utils import CommandExecResult, run_command


@dataclass
class VerifyResult:
    chisel_compile_to_verilog_success: bool = False
    compiled_verilog_code: str = ''

    sbt_cmd_exec_result: CommandExecResult = None
    iv_cmd_exec_result: CommandExecResult = None
    vvp_cmd_exec_result: CommandExecResult = None
    
    functionality_correct: bool = False

    @property
    def verilog_compile_success(self):
        # verilog_compile_success is True if the Icarus Verilog command executed successfully.
        # It means the Verilog code is **syntactically** correct.
        # NOTE: `verilog_compile_success` may be False even if Chisel code is syntactically correct
        # (i.e., `chisel_compile_to_verilog_success` is True).
        # This is because the Chisel code may generate Verilog code that is not compatible with
        # testbench or reference code, e.g., wrong module names, missing ports, etc.
        return self.iv_cmd_exec_result and self.iv_cmd_exec_result.is_ok
    
    @property
    def run_verilog_sim_success(self):
        # run_verilog_sim_success does not mean the functionality is correct.
        # It only means the simulation ran without errors.
        # The functionality correctness is evaluated separately and
        # stored in `functionality_correct`.
        return self.vvp_cmd_exec_result and self.vvp_cmd_exec_result.is_ok
    
    def __dict__(self):
        d = {
            'chisel_compile_to_verilog_success': self.chisel_compile_to_verilog_success,
            'verilog_compile_success': self.verilog_compile_success,
            'run_verilog_sim_success': self.run_verilog_sim_success,
            'functionality_correct': self.functionality_correct,
            #=
            'compiled_verilog_code': self.compiled_verilog_code,
        }
        d['sbt_cmd_exec_result'] = self.sbt_cmd_exec_result.__dict__ if self.sbt_cmd_exec_result else None
        d['iv_cmd_exec_result'] = self.iv_cmd_exec_result.__dict__ if self.iv_cmd_exec_result else None
        d['vvp_cmd_exec_result'] = self.vvp_cmd_exec_result.__dict__ if self.vvp_cmd_exec_result else None
        return d


class VerifierWorkingSpace:
    def __init__(self, chisel_dir: str | Path, iv_dir: str | Path, *, sbt_build_path: str | Path = 'build.sbt'):

        # Create directories if they don't exist
        self.chisel_dir = Path(chisel_dir)
        self.chisel_dir.mkdir(parents=True, exist_ok=True)
        self.iv_dir = Path(iv_dir)
        self.iv_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy sbt build file to chisel dir
        # Make sure the sbt build file exists
        sbt_build_path = Path(sbt_build_path)
        if not sbt_build_path.exists():
            raise FileNotFoundError(f"SBT build file not found: {sbt_build_path}")
        shutil.copy2(sbt_build_path, self.chisel_dir / "build.sbt")

        # Prepare the Chisel Main.scala file
        main_scala_path = self.chisel_dir / "src/main/scala/Main.scala"
        main_scala_path.parent.mkdir(parents=True, exist_ok=True)
        main_scala_path.touch()  # Create the file if it doesn't exist
    

class Verifier:
    def __init__(self, working_space: VerifierWorkingSpace, *, verbose: bool = False):
        self._working_space = working_space
        self._verbose = verbose

    @property
    def result(self):
        return self._result
    
    def _log(self, message: str):
        if self._verbose:
            # TODO: Can use `logging` module for better logging control
            print(f"[VERIFIER] {message}")

    def prepare(self, code: ChiselCode, testcase: Testcase):
        self._log("Preparing the verification environment...")
        # Initialize the result object
        self._result = VerifyResult()
        
        # Build Chisel's compiler env.
        # Write the Chisel code to the `src/main/scala/Main.scala` file.
        chisel_code_path = self._working_space.chisel_dir / "src/main/scala/Main.scala"
        chisel_code_path.write_text(code.decorated, encoding='utf-8')
        self._log(f"Chisel code written to {chisel_code_path}")
        
        # Move the reference code and testbench code to IV's working directory. 
        # All files in the `iv_dir` will be compiled by IV.
        self._log("Preparing reference and testbench code in IV working directory...")
        self._working_space.iv_dir.mkdir(parents=True, exist_ok=True)
        files_to_write = [
            (testcase.reference_code, f'{testcase.prob_id}_ref.sv'),
            (testcase.testbench_code, f'{testcase.prob_id}_tb.sv')
        ]
        for content, filename in files_to_write:
            if content:
                _target = self._working_space.iv_dir / filename
                _target.write_text(content, encoding='utf-8')
                self._log(f"Written {_target}")
        
        return True
    
    def chisel_compile_to_verilog(self):

        self._log("Compiling Chisel code to Verilog using SBT...")
        self._log(f"SBT command executed under working directory: {self._working_space.chisel_dir}")
        self._result.sbt_cmd_exec_result = run_command(
            'sbt run', workingdir=self._working_space.chisel_dir
        )
        self._log(f"SBT command executed with return code: {self._result.sbt_cmd_exec_result.return_code}")

        def _sbtout_clean(sbtout: str):
            # Remove the empty lines and all lines begin with `\s*| =>`
            sbtout = re.sub(r'^\s*\| =>.*\n', '', sbtout, flags=re.MULTILINE)
            sbtout = "\n".join(
                [line for line in sbtout.split('\n') if line.strip()]
            )
            # Remove all [info] lines and [warn] lines
            sbtout = re.sub(r'^\s*\[info\].*\n', '', sbtout, flags=re.MULTILINE)
            sbtout = re.sub(r'^\s*\[warn\].*\n', '', sbtout, flags=re.MULTILINE)
            return sbtout

        # Remove the empty lines and all lines begin with `\s*| =>`
        # by calling `_sbtout_clean`
        _o = self._result.sbt_cmd_exec_result.stdout
        self._result.sbt_cmd_exec_result.stdout = _sbtout_clean(_o)

        self._result.chisel_compile_to_verilog_success = self._result.sbt_cmd_exec_result.is_ok
        if not self._result.chisel_compile_to_verilog_success:
            self._log("Chisel compilation to Verilog failed.")
            return False

        # Extract Verilog code
        self._log("Extracting generated Verilog code...")
        generated_dir = self._working_space.chisel_dir / "generated"
        verilog_files = [
            f for f in generated_dir.iterdir() if f.suffix in {'.v', '.sv'}
        ]
        if len(verilog_files) != 1:
            raise RuntimeError(
                f"Expected exactly one Verilog file in {generated_dir}, "
                f"found: {[f.name for f in verilog_files]}"
            )
        
        # Read verilog code and store it in `compiled_verilog_code`
        self._log(f"Found generated Verilog file: {verilog_files[0]}")
        self._result.compiled_verilog_code = verilog_files[0].read_text(encoding='utf-8')
        self._result.chisel_compile_to_verilog_success = True
        return True

    def verilog_compile(self, output_fname: str = 'a.out', top_fname: str = 'top.v'):
        self._log("Compiling Verilog code using Icarus Verilog...")

        # Write the verilog code to the `iv_dir` as `top_fname`
        verilog_file = self._working_space.iv_dir / top_fname
        verilog_file.write_text(self._result.compiled_verilog_code)
        self._log(f"Verilog code written to {verilog_file}")

        # Find all files with .sv or .v extension in iv_dir
        # Generated verilog code is written in iv_dir by the last step.
        # The testbench and reference code files are already in iv_dir by prepare().
        all_verilog_files_under_iv = [
            f.relative_to(self._working_space.iv_dir)
            for f in self._working_space.iv_dir.iterdir() if f.suffix in {'.sv', '.v'}
        ]
        self._log(f"Icarus Verilog command executed under working directory: {self._working_space.iv_dir}")
        self._log(f"Found Verilog files for compilation: {[f.name for f in all_verilog_files_under_iv]}")
        
        # Compile
        # `-g2012` is used to enable SystemVerilog features.
        command = ['iverilog', '-g2012', '-o', output_fname, *all_verilog_files_under_iv]
        self._result.iv_cmd_exec_result = run_command(
            command, workingdir=self._working_space.iv_dir
        )
        self._log(f"Icarus Verilog command executed with return code: {self._result.iv_cmd_exec_result.return_code}")
        return self._result.verilog_compile_success

    def run_verilog_sim(self, output_fname: str = 'a.out'):
        self._log("Running Verilog simulation using VVP...")
        self._log(f"VVP command executed under working directory: {self._working_space.iv_dir}")
        self._result.vvp_cmd_exec_result = run_command(
            ['vvp', output_fname], workingdir=self._working_space.iv_dir
        )
        self._log(f"VVP command executed with return code: {self._result.vvp_cmd_exec_result.return_code}")
        return self._result.run_verilog_sim_success

    def functionality_eval(self, bm_type: Literal['autochip', 'verilog-eval']):

        self._log(f"Evaluating functionality for benchmark type: {bm_type}")
        sim_output = self._result.vvp_cmd_exec_result.stdout
        # AutoChip
        if bm_type == 'autochip':
            is_correct = "All tests passed!" in sim_output
        # Verilog Eval
        elif bm_type == 'verilog-eval':
            mismatch_pattern = re.compile(r'Mismatches: (\d+) in (\d+) samples')
            match = mismatch_pattern.search(sim_output)
            is_correct = match and int(match.group(1)) == 0
        else:
            raise ValueError(f"Unknown benchmark type: {bm_type}")
        
        self._log(f"Functionality evaluation result: {'Correct' if is_correct else 'Incorrect'}")
        self._result.functionality_correct = is_correct
        return is_correct
