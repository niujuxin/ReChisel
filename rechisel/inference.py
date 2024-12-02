
from rechisel.llm_client import get_model_completion

from rechisel.llm_utils import read_prompt, ModelMapping
from rechisel.benchmark import VerilogEvalCase
from rechisel.config import MODELSEL, PROMPTSEL

class InitGeneration:

    @staticmethod
    def basic(
        benchcase: VerilogEvalCase
    ):  
        system_prompt = read_prompt(PROMPTSEL.init_gen)
        model = ModelMapping[MODELSEL.init_gen]
        resp, _, _ = get_model_completion(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': benchcase.specification}
            ], model=model.value
        )
        return resp

