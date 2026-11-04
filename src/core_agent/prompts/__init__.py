"""What the model reads, one file per reader: `searcher`, `writer` and `judge`.

These are texts and tables of texts, with no logic. When each one enters the request is
decided by the roles (`roles/`) and the judge (`world/question_judge.py`), and none of these
files imports anything from the package. The sale line and the effects line live in
`writer` because the writer is the one who reads them. Changing a text here is
changing what the model sees, and that is measured with `evals/suite.py`.
"""
