
from functools import cached_property
import re


class ChiselCode:
    def __init__(
            self, 
            llm_response: str, 
            top_module_name: str
    ):
        self._llm_response = llm_response
        self._top_module_name = top_module_name
    
    @property
    def response(self) -> str:
        return self._llm_response
    
    @property
    def top_module_name(self) -> str:
        return self._top_module_name

    @cached_property
    def raw(self) -> str:
        
        chunks = re.findall(r'```scala', self._llm_response)
        # Raise error if no scala code block is found.
        if len(chunks) < 1:
            raise ValueError(f"Error: Scala code block is not found.")
        
        code_blocks = list()
        for match in re.finditer(r'```scala', self._llm_response):
            start = match.end()
            end = self._llm_response.find('```', start)
            if end == -1:
                raise ValueError(f"Error: Scala code block is not closed.")
            code_blocks.append(self._llm_response[start:end])
        
        code = "\n".join(code_blocks)
        return code
    
    @cached_property
    def raw_stripped(self) -> str:
        code = self.raw
        code = re.sub(r'^\s*import.*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*package.*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'object\s+\w+\s+extends\s+App\s*{.*}', '', code, flags=re.DOTALL)
        code = code.strip()
        return code
    
    @cached_property
    def decorated(self) -> str:
        return (
            f"package {self._top_module_name}\n\n"
            "import chisel3._\n"
            "import chisel3.util._\n\n"
            "import chisel3.stage.ChiselStage\n\n"
            #
            f"{self.raw_stripped}\n\n"
            #
            "object Main extends App {\n"
            "    (new ChiselStage).emitVerilog(\n"
            f"      new {self._top_module_name},\n"
            "      Array(\n"
            "        \"--target-dir\", \"generated\",\n"
            "        \"--emission-options=disableMemRandomization,disableRegisterRandomization\",\n"
            "      )\n"
            "    )\n"
            "}\n"
        )
