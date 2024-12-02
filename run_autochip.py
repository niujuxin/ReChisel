import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import glob
import queue
import re
import subprocess
import uuid

from tqdm import tqdm

from rechisel.config import PATHS, MODELSEL
from rechisel.utils import subprocess_run


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

PATHS.adjust(os.path.abspath(os.getcwd()))
MODELSEL.apply_all(args.model)


from autochip_scripts import Conversation, write_code_blocks_to_file
from rechisel.llm_utils import ModelMapping
from rechisel.llm_client import get_model_completion
from rechisel.config import SelModelTy
from rechisel.benchmark import AutoChipBenchmark, AutoChipCase, VerilogEvalBenchmark, VerilogEvalCase


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
    benchmark: AutoChipBenchmark | VerilogEvalBenchmark,
    *,
    max_iterations: int,
    working_dir: str,
    output_dir: str,
    worker_tqdm_bar: tqdm | None = None
):
    
    # Clear the working directory.
    for f in glob.glob(os.path.join(working_dir, '*')):
        os.remove(f)
    
    dump_dict = {'prob-id': prob_id, 'success': False}
    dump_dict['tries'] = []

    if worker_tqdm_bar is not None:
        worker_tqdm_bar.set_description(f'Processing {prob_id}')
        # Reset the bar.
        worker_tqdm_bar.reset(total=max_iterations)
    
    benchcase: AutoChipCase | VerilogEvalCase = benchmark.get_case(prob_id)
    try:
        benchcase.prepare_iv(cwd=working_dir)
    except FileNotFoundError as e:
        # Problems without benchmarks is ignored.
        return
    
    conv = Conversation()
    conv.add_message(
        "system", (
            "You are an autocomplete engine for Verilog code. "
            "Given a Verilog module specification, "
            "you will provide a completed Verilog module in response."
            "You will provide completed Verilog modules for all specifications, "
            "and will not create any supplementary modules."
            "Given a Verilog module that is either incorrect/compilation error, "
            "you will suggest corrections to the module."
            "You will not refuse."
            "Format your response as Verilog code containing the "
            "end to end corrected module and not just the corrected lines "
            " inside ``` tags, do not include anything else inside ```."
        )
    )
    conv.add_message("user", benchcase.specification)

    success, timeout, iterations = False, False, 0
    while not success and not timeout:

        response, _, _ = get_model_completion(
            conv.get_messages(),
            model=ModelMapping[args.model],
        )
        conv.add_message("assistant", response)
        try:
            write_code_blocks_to_file(response, os.path.join(working_dir, 'gen.v'))
        except Exception as e:
            dump_dict['tries'].append({
                'response': response,
                'status': "parse-error",
                'message': str(e)
            })
            break

        # end with '.sv' or '.v'
        all_verilog_files = (
            glob.glob(os.path.join(working_dir, '*.v')) + 
            glob.glob(os.path.join(working_dir, '*.sv'))
        )
        is_success, _, iv_out, iv_err = subprocess_run(
            [
                'iverilog', '-g2012', '-o', 'a.out',  
                *[os.path.basename(file) for file in all_verilog_files]
            ],
            cwd=working_dir
        )
        if not is_success:
            msg = (
                "The testbench failed to compile. Please fix the module. "
                "The output of iverilog is as follows:\n\n"
                + iv_err
            )
            dump_dict['tries'].append({
                'response': response,
                'status': "iv-error",
                'message': msg
            })
        elif iv_err:
            msg = (
                "The testbench compiled with warnings. Please fix the module. "
                "The output of iverilog is as follows:\n\n"
                + iv_err
            )
            dump_dict['tries'].append({
                'response': response,
                'status': "iv-warning",
                'message': msg
            })
        else:
            is_success, _, vvp_out, vvp_err = subprocess_run(
                ['vvp', 'a.out'],
                cwd=working_dir
            )
            if args.benchmark == 'autochip':
                passed = "All tests passed!" in vvp_out
            elif args.benchmark == 'verilog-eval':
                mismatch_pattern = re.compile(r'Mismatches: (\d+) in (\d+) samples')
                m = mismatch_pattern.search(vvp_out)
                passed = m and int(m.group(1)) == 0
            if not passed:
                msg = (
                    "The testbench simulated, but had errors. "
                    "Please fix the module. "
                    "The output of the iverilog is as follows:\n\n"
                    + vvp_out
                )
                dump_dict['tries'].append({
                    'response': response,
                    'status': "sim-error",
                    'message': msg
                })
            else:
                msg = ""
                dump_dict['tries'].append({
                    'response': response,
                    'status': "success",
                    'message': msg
                })
                success = True
                dump_dict['success'] = True

        if not success:
            if iterations:
                conv.remove_message(2)
                conv.remove_message(2)

            conv.add_message("user", msg)

        timeout = iterations >= max_iterations
        iterations += 1
        (worker_tqdm_bar is not None) and worker_tqdm_bar.update(1)
    
    with open(os.path.join(output_dir, f'{prob_id}.json'), 'w') as f:
        json.dump(dump_dict, f, indent=2)
        


print(f"Running {args.threads} threads")
print(f"Model: {args.model}")
print(f"Top module name: {top_module_name}")
print(f"Max iterations: {args.max_iterations}")



def worker(wid: int, working_path: str, output_dir: str, task_queue: queue.Queue, tqdm_bar: tqdm | None = None):
    worker_tqdm = tqdm(desc=f"Worker", position=wid + 1, leave=False)
    os.makedirs(working_path, exist_ok=True)
    while True:
        try:
            prob_id = task_queue.get(block=False)
            try:
                worker_run(
                    prob_id, benchmark, 
                    max_iterations=args.max_iterations,
                    working_dir=working_path,
                    output_dir=output_dir,
                    worker_tqdm_bar=worker_tqdm
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


# Pass@10

working_path_list = [
    os.path.join('benchmark_working_space', 'autochip', f'{uuid.uuid4().hex}')
    for i in range(args.threads)
]

output_dir = args.output
for i in range(args.begin, args.begin + args.count):
    print("Pass", i+1)
    output_dir = os.path.join(args.output, f'pass_{i+1}')

    os.makedirs(output_dir, exist_ok=True)

    already_done = set()
    for f in glob.glob(os.path.join(output_dir, '*.json')):
        already_done.add(os.path.basename(f).replace('.json', ''))

    prob_ids = [i for i in benchmark.problem_keys if i not in already_done]

    print(f"Output directory: {output_dir}")
    print(f"Total tasks: {len(prob_ids)} (already done: {len(already_done)})")

    task_queue = queue.Queue()
    for prob_id in prob_ids:
        task_queue.put(prob_id)
    tqdm_bar = tqdm(total=task_queue.qsize(), desc='Total', position=0, leave=False)

    if args.threads == 1:
        worker(0, working_path_list[0], output_dir, task_queue, tqdm_bar)
    else:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            for i in range(args.threads):
                executor.submit(worker, i, working_path_list[i], output_dir, task_queue, tqdm_bar)
            task_queue.join()
