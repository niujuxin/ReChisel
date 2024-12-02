from enum import StrEnum
from functools import cached_property, lru_cache
import os
import re
from typing import Dict, Literal

from rechisel.config import PATHS


@lru_cache()
def read_prompt(prompt_key: str):
    try:
        with open(os.path.join(PATHS.prompt_pool, f'{prompt_key}.txt'), 'r') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cannot find prompt file: {prompt_key}.txt"
        )
        

class ModelMapping(StrEnum):
    gpt4omini = 'gpt-4o-mini'
    gpt4o = 'gpt-4o'
    gpt4turbo = 'gpt-4-turbo'
    gpt35turbo = 'gpt-3.5-turbo'
    claude35sonnet = 'anthropic.claude-3-5-sonnet-20241022-v2:0'
    claude35haiku = 'anthropic.claude-3-5-haiku-20241022-v2:0'


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
            return ""
        
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
        code = re.sub(r'object\s+\w+\s+extends\s+App\s*{.*?}', '', code, flags=re.DOTALL)
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
            "object Main extends App {{\n"
            "    (new ChiselStage).emitVerilog(\n"
            f"      new {self._top_module_name},\n"
            "      Array(\n"
            "        \"--target-dir\", \"generated\",\n"
            "        \"--emission-options=disableMemRandomization,disableRegisterRandomization\",\n"
            "      )\n"
            "    )\n"
            "}}\n"
        )


class Traces:
    def __init__(self, max_traces: int = 4):
        self._traces = list()
        self._max_traces = max_traces

    def add_trace(self, message: Dict[str, str]):
        self._traces.append(message)
        if len(self._traces) > self._max_traces:
            self._traces.pop(0)

    def get_traces(self):
        return self._traces
