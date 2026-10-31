"""Print how the golden set is scored.

Retrieval runs inside pytest (no model, same result every time):

    cd backend && python -m pytest tests/test_eval.py -s
"""

from evals.score import load

corpus, questions = load()
print(f"{len(questions)} questions over {len(corpus)} cards")
print("Score retrieval with: python -m pytest tests/test_eval.py -s")
