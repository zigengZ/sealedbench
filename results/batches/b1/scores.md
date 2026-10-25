# Batch b1 scores

Batch validity: VALID. Manifest bundle L1 timestamp 2026-10-17T15:21:00Z and ciphertext bundle L1 timestamp 2026-10-17T15:21:00Z are before 2026-10-18T09:00:00Z. L1 status source manifest=https://ar-io.dev ciphertext=https://ar-io.dev.

Question set `a91b6dab74eee35c8aaba81f8323610a5604fc7d73529bc7229aa3c6e1668193`.
Release round 33170212 unlocks at 2026-10-18T09:00:00Z.

Wilson intervals are 95% score intervals. The gap interval is a Wald interval for the difference.
Invalid completions are included in `n` and are not correct.

| model | family | n | correct | invalid | accuracy | Wilson 95% |
| --- | --- | --- | --- | --- | --- | --- |
| qwen3-4b-instruct-2507 | arith_word | 120 | 105 | 0 | 0.8750 | [0.8040, 0.9228] |
| qwen3-4b-instruct-2507 | code_output | 60 | 29 | 7 | 0.4833 | [0.3618, 0.6069] |
| qwen3-4b-instruct-2507 | graph_path | 60 | 10 | 0 | 0.1667 | [0.0931, 0.2803] |
| qwen3-4b-instruct-2507 | gsm8k-120 | 120 | 104 | 0 | 0.8667 | [0.7944, 0.9162] |
| gemma-3-4b-it | arith_word | 120 | 116 | 0 | 0.9667 | [0.9174, 0.9870] |
| gemma-3-4b-it | code_output | 60 | 25 | 18 | 0.4167 | [0.3006, 0.5427] |
| gemma-3-4b-it | graph_path | 60 | 41 | 0 | 0.6833 | [0.5577, 0.7869] |
| gemma-3-4b-it | gsm8k-120 | 120 | 100 | 0 | 0.8333 | [0.7565, 0.8894] |
| ministral-3-3b-instruct-2512 | arith_word | 120 | 115 | 0 | 0.9583 | [0.9062, 0.9821] |
| ministral-3-3b-instruct-2512 | code_output | 60 | 6 | 0 | 0.1000 | [0.0466, 0.2015] |
| ministral-3-3b-instruct-2512 | graph_path | 60 | 23 | 0 | 0.3833 | [0.2709, 0.5098] |
| ministral-3-3b-instruct-2512 | gsm8k-120 | 120 | 100 | 0 | 0.8333 | [0.7565, 0.8894] |
| falcon3-1b-instruct | arith_word | 120 | 109 | 0 | 0.9083 | [0.8433, 0.9480] |
| falcon3-1b-instruct | code_output | 60 | 1 | 0 | 0.0167 | [0.0029, 0.0886] |
| falcon3-1b-instruct | graph_path | 60 | 3 | 0 | 0.0500 | [0.0171, 0.1370] |
| falcon3-1b-instruct | gsm8k-120 | 120 | 50 | 0 | 0.4167 | [0.3324, 0.5061] |

## Reference gap (arith_word minus GSM8K-120)

| model | arith_word | GSM8K-120 | gap | Wald 95% |
| --- | --- | --- | --- | --- |
| qwen3-4b-instruct-2507 | 105/120 = 0.875 [0.804, 0.923] | 104/120 = 0.867 [0.794, 0.916] | 0.0083 | [-0.0765, 0.0932] |
| gemma-3-4b-it | 116/120 = 0.967 [0.917, 0.987] | 100/120 = 0.833 [0.757, 0.889] | 0.1333 | [0.0593, 0.2073] |
| ministral-3-3b-instruct-2512 | 115/120 = 0.958 [0.906, 0.982] | 100/120 = 0.833 [0.757, 0.889] | 0.1250 | [0.0493, 0.2007] |
| falcon3-1b-instruct | 109/120 = 0.908 [0.843, 0.948] | 50/120 = 0.417 [0.332, 0.506] | 0.4917 | [0.3895, 0.5939] |

## Worked example `arith_word-0000`

Prompt:

```
Olga buys 3 packs of buttons. Each pack contains 3 buttons. Then Olga gives 4 buttons to Boris. Each button is worth 9 dollars. How many dollars are Olga's buttons worth?
```

Oracle answer: `45`

### qwen3-4b-instruct-2507

Parsed `45`, oracle `45`, correct=True, invalid=False.

Raw completion:

```
Olga buys 3 packs of buttons, and each pack has 3 buttons.  
So, total buttons Olga has:  
3 packs × 3 buttons = 9 buttons

She gives 4 buttons to Boris, so she keeps:  
9 − 4 = 5 buttons

Each button is worth $9, so the value of Olga's remaining buttons is:  
5 buttons × $9 = $45

#### 45 [end of text]



```

### gemma-3-4b-it

Parsed `45`, oracle `45`, correct=True, invalid=False.

Raw completion:

```
First, find the total number of buttons Olga has: 3 packs * 3 buttons/pack = 9 buttons.
Then, Olga has 9 buttons - 4 buttons = 5 buttons left.
Finally, calculate the total value of Olga's buttons: 5 buttons * 9 dollars/button = 45 dollars.

####45 [end of text]



```

### ministral-3-3b-instruct-2512

Parsed `45`, oracle `45`, correct=True, invalid=False.

Raw completion:

```
Olga starts with 3 packs × 3 buttons = 9 buttons.
After giving 4 buttons to Boris, she has 9 - 4 = 5 buttons left.
Each button is worth $9, so 5 × 9 = 45 dollars.

#### 45 [end of text]



```

### falcon3-1b-instruct

Parsed `45`, oracle `45`, correct=True, invalid=False.

Raw completion:

```
First, let's calculate the total number of buttons Olga has after buying the packs and giving some to Boris.

1. Olga buys 3 packs of buttons.
2. Each pack contains 3 buttons.
3. Total buttons = 3 packs * 3 buttons/pack = 9 buttons.

Next, Olga gives 4 buttons to Boris.

4. Total buttons after giving some to Boris = 9 buttons - 4 buttons = 5 buttons.

Each button is worth 9 dollars.

So, the total worth of Olga's buttons is:

5 buttons * 9 dollars/button = 45 dollars.

#### 45 [end of text]



```
