
from functools import cached_property, lru_cache
import json
import glob
import os


class AutoChipEval:

    def __init__(self, eval_fpath: str):
        self._eval_fpath = eval_fpath
        self._testcases = [
            os.path.basename(f).replace('.json', '')
            for f in glob.glob(f"{self._eval_fpath}/*.json")
        ]

    @cached_property
    def testcases(self):
        return tuple(self._testcases)

    @lru_cache
    def get_case(self, prob_id: str):
        with open(f"{self._eval_fpath}/{prob_id}.json") as f:
            return json.load(f)

    def __len__(self):
        return len(self.testcases)

    @cached_property
    def first_successed(self):
        return [
            prob_id
            for prob_id in self.testcases
            if (c:=self.get_case(prob_id))['success'] and len(c['tries']) == 1
        ]

    @cached_property
    def successed(self):
        return [
            prob_id
            for prob_id in self.testcases
            if self.get_case(prob_id)['success']
        ]

    @cached_property
    def failed(self):
        return [
            prob_id
            for prob_id in self.testcases
            if prob_id not in self.successed
        ]



class OursEval:

    def __init__(self, eval_fpath: str):
        self._eval_fpath = eval_fpath
        self._testcases = [
            os.path.basename(f).replace('.json', '')
            for f in glob.glob(f"{self._eval_fpath}/*.json")
        ]

    @cached_property
    def testcases(self):
        return tuple(self._testcases)

    @lru_cache
    def get_case(self, prob_id: str):
        with open(f"{self._eval_fpath}/{prob_id}.json") as f:
            return json.load(f)

    def __len__(self):
        return len(self.testcases)

    @cached_property
    def first_successed(self):
        return [
            prob_id
            for prob_id in self.testcases
            if (c:=self.get_case(prob_id))['success'] and len(c['tries']) == 0
        ]

    @cached_property
    def successed(self):
        return [
            prob_id
            for prob_id in self.testcases
            if self.get_case(prob_id)['success']
        ]

    @cached_property
    def failed(self):
        return [
            prob_id
            for prob_id in self.testcases
            if not self.get_case(prob_id)['success']
        ]
