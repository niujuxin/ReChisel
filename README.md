# ReChisel

Code for paper 'ReChisel: Effective Automatic Chisel Code Generation by LLM with Reflection'.


```
python rechisel_cli.py \
--prob-id Prob030_popcount255 \
--specification benchmarks/VerilogEval_Prob030/Prob030_popcount255_spec.txt \
--reference benchmarks/VerilogEval_Prob030/Prob030_popcount255_ref.sv \
--testbench benchmarks/VerilogEval_Prob030/Prob030_popcount255_tb.sv \
--top-module-name TopModule \
--bm-type verilog-eval \
--use-in-context-history --use-llm-summary \
--verifier-working-dir output/VerilogEval_Prob030 \
--output output/VerilogEval_Prob030/result.json
```
