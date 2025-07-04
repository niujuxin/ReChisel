from pathlib import Path
from functools import cached_property
from typing import Optional

class Testcase:
    def __init__(
        self, 
        prob_id: str, 
        specification_dir: Optional[str | Path] = None,
        reference_dir: Optional[str | Path] = None,
        testbench_dir: Optional[str | Path] = None,
    ):
        self.prob_id = prob_id
        self._specification_dir = Path(specification_dir) if specification_dir else None
        self._reference_dir = Path(reference_dir) if reference_dir else None
        self._testbench_dir = Path(testbench_dir) if testbench_dir else None

    def _read_file_safe(self, file_path: Optional[Path]) -> str:
        """ Safely read file content, return empty string if path is None or file doesn't exist """
        if not file_path:
            return ""
        try:
            return file_path.read_text(encoding='utf-8')
        except (FileNotFoundError, IOError):
            return ""

    @cached_property
    def specification(self) -> str:
        return self._read_file_safe(self._specification_dir)

    @cached_property
    def reference_code(self) -> str:
        return self._read_file_safe(self._reference_dir)

    @cached_property
    def testbench_code(self) -> str:
        return self._read_file_safe(self._testbench_dir)
