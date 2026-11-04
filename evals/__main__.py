"""`uv run python -m evals`: the quality suite (see `evals/suite.py`)."""

import asyncio
import sys

from evals.suite import main

asyncio.run(main(sys.argv[1:]))
