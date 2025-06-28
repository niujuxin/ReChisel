from pathlib import Path
from functools import cached_property
from typing import Optional

class BenchmarkCase:
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

    @cached_property
    def specification(self) -> str:
        return self._read_file_safe(self._specification_dir)

    @cached_property
    def reference_code(self) -> str:
        return self._read_file_safe(self._reference_dir)

    @cached_property
    def testbench_code(self) -> str:
        return self._read_file_safe(self._testbench_dir)

    def _read_file_safe(self, file_path: Optional[Path]) -> str:
        """ Safely read file content, return empty string if path is None or file doesn't exist """
        if not file_path:
            return ""
        try:
            return file_path.read_text(encoding='utf-8')
        except (FileNotFoundError, IOError):
            return ""

    def prepare_iv(self, iv_working_dir: str | Path) -> bool:
        """ Move the reference code and testbench code to IV's working directory. """
        if isinstance(iv_working_dir, str):
            iv_working_dir = Path(iv_working_dir)
        iv_working_dir.mkdir(parents=True, exist_ok=True)
        
        files_to_write = [
            (self.reference_code, f'{self.prob_id}_ref.sv'),
            (self.testbench_code, f'{self.prob_id}_tb.sv')
        ]
        for content, filename in files_to_write:
            if content:
                target_file = iv_working_dir / filename
                target_file.write_text(content, encoding='utf-8')
        
        return True
    