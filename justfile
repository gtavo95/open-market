# What has to be green before a PR. `typecheck` whole does not go in yet: mypy still gives
# errors on main. It goes into `ci` when it is green.
ci: secret-scan okf test

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
