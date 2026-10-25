# Generator entropy

Seeds are `SHA-256("sealedbench/v1/entropy\n" || family || "\n" || index)`.
Jaccard is the mean, over seeds, of the mean pairwise Jaccard of prompt token sets.
Gate: at least 999 distinct question-set hashes out of 1000 seeds.

| family | seeds | n | distinct sets | distinct prompts | mean Jaccard | unique answers | seconds | gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| arith_word | 1000 | 40 | 1000 | 39894 | 0.2336 | 751 | 2.039 | PASS |
| code_output | 1000 | 40 | 1000 | 30602 | 0.5677 | 16213 | 184.717 | PASS |
| graph_path | 1000 | 40 | 1000 | 40000 | 0.5837 | 37 | 8.179 | PASS |
