import re
import subprocess
from typing import Tuple, Optional, Union


def run_command(
    command: Union[str, list],
    *,
    workingdir: Optional[str] = None,
    raise_on_error: bool = False,
    io_encoding: str = 'utf-8',
    use_shell: bool = False,
    env: Optional[dict] = None,
    timeout: Optional[int] = None,
) -> Tuple[int, str, str]:
    """
    Runs a command synchronously and returns (returncode, stdout, stderr), 
    with ANSI escape sequences removed. Optionally raises an exception if
    the return code is not zero.

    Args:
        command: Command to be executed. Can be a string or list of strings.
        workingdir: Working directory where the command should be executed.
        raise_on_error: If True, will raise CalledProcessError when the command 
            returns a non-zero status (default: False).
        io_encoding: Encoding used to decode stdout and stderr (default: 'utf-8').
        use_shell: If True, the command will be executed in a shell 
            (e.g., /bin/sh on Unix) (default: False).
        env: Dictionary for the child process's environment variables (default: None).
        timeout: Timeout in seconds; if exceeded, a TimeoutExpired exception is raised (default: None).

    Returns:
        A tuple (returncode, stdout, stderr) for the command executed.

    Raises:
        subprocess.CalledProcessError: If raise_on_error is True and the command 
            exits with a non-zero return code.
        subprocess.TimeoutExpired: If the command does not complete before the 
            timeout duration.
    """
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

    # If we're not using a shell, and the command is given as a string,
    # let's split it into a list so it can be executed properly
    if not use_shell and isinstance(command, str):
        command = command.split()

    result = subprocess.run(
        command,
        cwd=workingdir,
        check=raise_on_error,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=use_shell,
        env=env,
        encoding=io_encoding,
        timeout=timeout,
    )
    
    # Clean out ANSI escape sequences from stdout/stderr
    stdout_clean = ansi_escape.sub('', result.stdout if result.stdout else '')
    stderr_clean = ansi_escape.sub('', result.stderr if result.stderr else '')

    return result.returncode, stdout_clean, stderr_clean
