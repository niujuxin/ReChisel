python run_autochip.py \
    -m gpt4omini -o results/autochip/ --benchmark verilog-eval \
    --begin 0 --count 1 \
    --thread 1

python run_rechisel.py \
    -m gpt4omini -o results/rechisel/ --benchmark autochip \
    --begin 0 --count 1 \
    --thread 1
