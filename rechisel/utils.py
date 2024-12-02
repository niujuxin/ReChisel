
import os
import re
import subprocess
from typing import Optional



def subprocess_run(
        command: list[str], cwd: Optional[str] = None, *,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25
):
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=stdout, stderr=stderr, text=text,
            timeout=timeout,
            encoding='utf-8',
            # For Windows, we need to set the shell to True
            shell=True if os.name == 'nt' else False,
            errors='replace'
        )
    except subprocess.TimeoutExpired:
        return False, -1, '', 'TimeoutExpired'
    else:
        output, error = result.stdout, result.stderr
        output = output if output else ''
        error = error if error else ''
        # Remove ANSI escape sequences from the output
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        output = ansi_escape.sub('', output)
        error = ansi_escape.sub('', error)
        if os.name == 'nt':
            output = output.replace('\r', '').replace('\x1b', '')
            error = error.replace('\r', '').replace('\x1b', '')
        return result.returncode == 0, result.returncode, output, error



