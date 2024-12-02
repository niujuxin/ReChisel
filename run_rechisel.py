
import json
import os
import argparse

import queue
import glob
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from rechisel.config import PATHS, MODELSEL
from rechisel.inference import InitGeneration
from rechisel.llm_utils import ChiselCode
from rechisel.verify import Verifier, VerifyWorkingSpace
from rechisel.benchmark import AutoChipBenchmark, VerilogEvalBenchmark
from core import functinoality_correction, syntax_correction, verification


argparser = argparse.ArgumentParser()
argparser.add_argument('-m', '--model', type=str)
argparser.add_argument('-o', '--output', type=str)
argparser.add_argument('--benchmark', type=str, choices=['verilog-eval', 'autochip'])
argparser.add_argument('--max-iterations', type=int, default=10)
# Control Pass@k
# Will process from Pass@begin to Pass@begin+count
argparser.add_argument('--begin', type=int, default=0)
argparser.add_argument('--count', type=int, default=10)
# On Error:
#  - skip: Skip the current problem and continue with the next problem.
#  - raise: Raise an exception and stop the process.
argparser.add_argument('--onerror', type=str, choices=['skip', 'raise'], default='raise')
# Threads
argparser.add_argument('--threads', type=int, default=1)

args = argparser.parse_args()


if False and args.benchmark_dir:  # Deprecated
    PATHS.verilog_eval_benchmark = args.benchmark_dir
PATHS.adjust(os.path.abspath(os.getcwd()))
MODELSEL.apply_all(args.model)


benchmark: AutoChipBenchmark | VerilogEvalBenchmark = {
    'verilog-eval': VerilogEvalBenchmark(),
    'autochip': AutoChipBenchmark()
}.get(args.benchmark)
top_module_name = {
    'verilog-eval': 'TopModule',
    'autochip': 'top_module',
}.get(args.benchmark)


def worker_run(
    prob_id: str,
    output_dir: str,
    benchmark: VerilogEvalBenchmark,
    verifier: Verifier,
    max_iterations: int,
    *,
    tqdm_bar: tqdm | None = None
):
    if tqdm_bar is not None:
        tqdm_bar.set_description(f'Processing {prob_id}')
        # Reset the bar.
        tqdm_bar.reset(total=max_iterations + 1)
    benchcase = benchmark.get_case(prob_id)
    result_dict = {'prob-id': prob_id,}
    result_dict['success'] = False

    init_response = InitGeneration.basic(benchcase)
    chisel_code = ChiselCode(init_response, top_module_name)
    verify_result = verification(benchcase, chisel_code, verifier)
    tqdm_bar and tqdm_bar.update(1)

    result_dict['initial-generation'] = init_response
    result_dict['initial-verify-result'] = verify_result.__dict__

    result_dict['tries'] = list()
    maximum_iterations = max_iterations
    trail_count = 0
    while True:

        if not verify_result.syntax_correct:

            correction_result = syntax_correction(
                benchcase, chisel_code, verify_result,
            )
            chisel_code = ChiselCode(correction_result.syntax_correction, top_module_name)
            verify_result = verification(benchcase, chisel_code, verifier)
            result_dict['tries'].append({
                'type': 'syntax',
                'correction-result': correction_result.__dict__,
                'verify-result': verify_result.__dict__,
            })
        
        elif not verify_result.functionality_correct:

            correction_result = functinoality_correction(
                benchcase, chisel_code, verify_result,
            )
            chisel_code = ChiselCode(correction_result.functionality_correction, top_module_name)
            verify_result = verification(benchcase, chisel_code, verifier)
            result_dict['tries'].append({
                'type': 'functionality',
                'correction-result': correction_result.__dict__,
                'verify-result': verify_result.__dict__,
            })
        
        else:
            result_dict['success'] = True
            break
        
        tqdm_bar and tqdm_bar.update(1)
        trail_count += 1
        if trail_count >= maximum_iterations:
            break

    with open(os.path.join(output_dir, f'{prob_id}.json'), 'w') as f:
        json.dump(result_dict, f, indent=2)


print(f'Model: {args.model}')
print(f"Top module name: {top_module_name}")
print(f'Max iterations: {args.max_iterations}')



def worker(wid: int, output_dir: str, working_space: VerifyWorkingSpace, tqdm_bar: tqdm | None = None):
    worker_tqdm = tqdm(desc='Worker', position=wid + 1)
    verifier = Verifier(working_space, benchmark=args.benchmark)
    while True:
        try:
            prob_id = task_queue.get(block=False)
            try:
                worker_run(
                    prob_id, output_dir, benchmark, verifier, args.max_iterations,
                    tqdm_bar=worker_tqdm
                )
            except Exception as e:
                if args.onerror == 'raise':
                    raise e
                elif args.onerror == 'skip':
                    pass
            else:
                tqdm_bar.update(1)
            task_queue.task_done()
        except queue.Empty:
            break


working_space_list = [VerifyWorkingSpace() for _ in range(args.threads)]


# Pass@10

for i in range(args.begin, args.begin + args.count):
    output_dir = os.path.join(args.output, f'pass_{i+1}')
    os.makedirs(output_dir, exist_ok=True)
    already_done = set()
    for f in glob.glob(os.path.join(output_dir, '*.json')):
        already_done.add(os.path.basename(f).replace('.json', ''))
        
    prob_ids = [k for k in benchmark.problem_keys if k not in already_done]

    task_queue = queue.Queue()
    for prob_id in prob_ids:
        task_queue.put(prob_id)

    print(f'Output directory: {output_dir}')
    print(f'Running {task_queue.qsize()} tasks with {args.threads} threads')
    print(f"Total tasks: {task_queue.qsize()} (already done: {len(already_done)})")

    tqdm_bar = tqdm(total=task_queue.qsize(), desc='Total', position=0)

    if args.threads == 1:
        worker(0, output_dir, working_space_list[0], tqdm_bar)
    else:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            for idx in range(args.threads):
                executor.submit(worker, idx, output_dir, working_space_list[idx], tqdm_bar)
            task_queue.join()
