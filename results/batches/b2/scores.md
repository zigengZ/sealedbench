# b2

{"batch_valid":null}

## qwen3-4b-instruct-2507 (COMPLETE)
- arith_word: n=80 correct=0 invalid=80 truncated=0 accuracy=0.0 among_parsed=None
- code_output: n=30 correct=18 invalid=12 truncated=12 accuracy=0.6 among_parsed=1.0
- graph_path: n=30 correct=1 invalid=29 truncated=24 accuracy=0.0333 among_parsed=1.0
- gsm8k: n=80 correct=3 invalid=76 truncated=0 accuracy=0.0375 among_parsed=0.75
- arith minus gsm8k: -0.0375 newcombe95=[-0.10454720090045116, 0.014535415675296967]

## gemma-3-4b-it (COMPLETE)
- arith_word: n=80 correct=0 invalid=80 truncated=0 accuracy=0.0 among_parsed=None
- code_output: n=30 correct=14 invalid=13 truncated=13 accuracy=0.4667 among_parsed=0.8235294117647058
- graph_path: n=30 correct=0 invalid=30 truncated=0 accuracy=0.0 among_parsed=None
- gsm8k: n=80 correct=0 invalid=80 truncated=2 accuracy=0.0 among_parsed=None
- arith minus gsm8k: 0.0 newcombe95=[-0.0458181295355271, 0.0458181295355271]

## ministral-3-3b-instruct-2512 (COMPLETE)
- arith_word: n=80 correct=0 invalid=80 truncated=0 accuracy=0.0 among_parsed=None
- code_output: n=30 correct=2 invalid=0 truncated=0 accuracy=0.0667 among_parsed=0.06666666666666667
- graph_path: n=30 correct=0 invalid=30 truncated=2 accuracy=0.0 among_parsed=None
- gsm8k: n=80 correct=0 invalid=80 truncated=1 accuracy=0.0 among_parsed=None
- arith minus gsm8k: 0.0 newcombe95=[-0.0458181295355271, 0.0458181295355271]

## falcon3-1b-instruct (COMPLETE)
- arith_word: n=80 correct=1 invalid=79 truncated=0 accuracy=0.0125 among_parsed=1.0
- code_output: n=30 correct=2 invalid=0 truncated=0 accuracy=0.0667 among_parsed=0.06666666666666667
- graph_path: n=30 correct=0 invalid=27 truncated=1 accuracy=0.0 among_parsed=0.0
- gsm8k: n=80 correct=0 invalid=79 truncated=1 accuracy=0.0 among_parsed=0.0
- arith minus gsm8k: 0.0125 newcombe95=[-0.03445940372198131, 0.06746270077668666]

# POST-HOC sentinel normalization

Not the registered primary endpoint. The registered scores above are unchanged.
Same items, same truncation rule on the raw stdout, with the b3 grader-input normalization from sealedbench/v2/grade_b3.py applied before the registered integer and code rules. Not the registered primary endpoint.

## POST-HOC qwen3-4b-instruct-2507
- arith_word: n=80 correct=73 invalid=0 truncated=0 accuracy=0.9125 among_parsed=0.9125
- code_output: n=30 correct=18 invalid=12 truncated=12 accuracy=0.6 among_parsed=1.0
- graph_path: n=30 correct=6 invalid=24 truncated=24 accuracy=0.2 among_parsed=1.0
- gsm8k: n=80 correct=77 invalid=0 truncated=0 accuracy=0.9625 among_parsed=0.9625
- arith minus gsm8k: -0.050000000000000044 newcombe95=[-0.13588597047360562, 0.030453278454617205]

## POST-HOC gemma-3-4b-it
- arith_word: n=80 correct=15 invalid=64 truncated=0 accuracy=0.1875 among_parsed=0.9375
- code_output: n=30 correct=14 invalid=13 truncated=13 accuracy=0.4667 among_parsed=0.8235294117647058
- graph_path: n=30 correct=21 invalid=0 truncated=0 accuracy=0.7 among_parsed=0.7
- gsm8k: n=80 correct=26 invalid=50 truncated=2 accuracy=0.325 among_parsed=0.8666666666666667
- arith minus gsm8k: -0.1375 newcombe95=[-0.26694334579582835, -0.0019103996304833948]

## POST-HOC ministral-3-3b-instruct-2512
- arith_word: n=80 correct=73 invalid=0 truncated=0 accuracy=0.9125 among_parsed=0.9125
- code_output: n=30 correct=2 invalid=0 truncated=0 accuracy=0.0667 among_parsed=0.06666666666666667
- graph_path: n=30 correct=17 invalid=2 truncated=2 accuracy=0.5667 among_parsed=0.6071428571428571
- gsm8k: n=80 correct=65 invalid=4 truncated=1 accuracy=0.8125 among_parsed=0.8552631578947368
- arith minus gsm8k: 0.09999999999999998 newcombe95=[-0.008308732314132358, 0.20860427522677194]

## POST-HOC falcon3-1b-instruct
- arith_word: n=80 correct=56 invalid=12 truncated=0 accuracy=0.7 among_parsed=0.8235294117647058
- code_output: n=30 correct=2 invalid=0 truncated=0 accuracy=0.0667 among_parsed=0.06666666666666667
- graph_path: n=30 correct=1 invalid=13 truncated=1 accuracy=0.0333 among_parsed=0.058823529411764705
- gsm8k: n=80 correct=21 invalid=30 truncated=1 accuracy=0.2625 among_parsed=0.42
- arith minus gsm8k: 0.43749999999999994 newcombe95=[0.2866172484138846, 0.5600877630684398]
