from pathlib import Path
from functools import cached_property
from typing import Optional

class Testcase:
    def __init__(
        self, 
        prob_id: str, 
        specification_path: Optional[str | Path] = None,
        reference_path: Optional[str | Path] = None,
        testbench_path: Optional[str | Path] = None,
    ):
        self.prob_id = prob_id
        self._specification_path = Path(specification_path) if specification_path else None
        self._reference_path = Path(reference_path) if reference_path else None
        self._testbench_path = Path(testbench_path) if testbench_path else None

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
        return self._read_file_safe(self._specification_path)

    @cached_property
    def reference_code(self) -> str:
        return self._read_file_safe(self._reference_path)

    @cached_property
    def testbench_code(self) -> str:
        return self._read_file_safe(self._testbench_path)

    def to_dict(self) -> dict:
        """ Convert the Testcase instance to a dictionary representation """
        return {
            'prob_id': self.prob_id,
            'specification_path': str(self._specification_path) if self._specification_path else None,
            'reference_path': str(self._reference_path) if self._reference_path else None,
            'testbench_path': str(self._testbench_path) if self._testbench_path else None,
        }

    def __str__(self) -> str:
        return (
            f"Testcase(prob_id={self.prob_id}, "
            f"specification_path={self._specification_path}, "
            f"reference_path={self._reference_path}, "
            f"testbench_path={self._testbench_path})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()
