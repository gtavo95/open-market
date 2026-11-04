# Everything goes inside the image: catalejo as a wheel in vendor/ and the catalog as a
# bundle in okf/ (`core_agent/` is code of this repo). There is
# nothing to mount, which is what Cloud Run needs.
#
#   docker run --rm -p 8000:8000 -e MUSE_API_KEY=$MUSE_API_KEY open-market
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# The deps go before the code: changing main.py reinstalls nothing. --locked
# cuts the build if uv.lock does not match pyproject.toml or the hash of the
# wheel in vendor/, which is what happens if catalejo was rebuilt without running the script.
COPY pyproject.toml uv.lock ./
COPY vendor/ vendor/
RUN uv sync --locked --no-dev

COPY . .

RUN useradd --create-home --uid 1000 demo && chown -R demo:demo /app
USER demo

EXPOSE 8000

# A single worker: the slot semaphore lives in the process, and each extra worker
# loads the 360 KB again and opens its own httpx client. It scales with SLOTS.
CMD ["uvicorn", "main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
