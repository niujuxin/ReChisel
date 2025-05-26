from pathlib import Path
from functools import cached_property
from typing import Optional

class BenchmarkCase:
    def __init__(
        self, 
        prob_id: str, 
        specification_dir: Optional[str] = None,
        reference_dir: Optional[str] = None,
        testbench_dir: Optional[str] = None,
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
        """Safely read file content, return empty string if path is None or file doesn't exist"""
        if not file_path:
            return ""
        try:
            return file_path.read_text(encoding='utf-8')
        except (FileNotFoundError, IOError):
            return ""

    def prepare_iv(self, target_dir: str) -> bool:
        """Prepare IV files to target directory"""
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        
        files_to_write = [
            (self._reference_dir, self.reference_code, f'{self.prob_id}_ref.sv'),
            (self._testbench_dir, self.testbench_code, f'{self.prob_id}_tb.sv')
        ]
        
        for source_dir, content, filename in files_to_write:
            if source_dir and content:
                target_file = target_path / filename
                target_file.write_text(content, encoding='utf-8')
        
        return True
    