# What has to be green before a PR. `test` and `typecheck` whole do not go in yet:
# on main two tests in `tests/evals/` fail (the bundle does not bring `evals/cases.tsv` or
# `evals/flows.tsv`) and mypy gives 31 errors. They go into `ci` when they are green.
ci: secret-scan okf

# The rules first, with their failing cases; then the repo.
secret-scan:
    uv run pytest -q tests/scripts
    uv run mypy -m scripts.secret_scan -m tests.scripts.test_secret_scan
    uv run python scripts/secret_scan.py

okf:
    okf/verify.sh

test:
    uv run pytest

typecheck:
    uv run mypy
