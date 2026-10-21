#
# Based on the Dockerfile from this project - https://github.com/bmaingret/coach-planner
#

# the wheel is pure python, so it is built once on the build platform
FROM --platform=$BUILDPLATFORM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv build --wheel \
 && uv export --frozen --no-dev --no-emit-project --format requirements-txt -o dist/requirements.txt

FROM python:3.14-slim AS runner

RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

WORKDIR /app
COPY --from=builder /app/dist /tmp/dist
# Install the locked dependencies (hash checked), then the built package so the CLI entrypoint is available.
# pip is removed afterwards: the CLI does not need it, and it vendors its own copies of certifi and urllib3.
RUN pip install --no-cache-dir --require-hashes -r /tmp/dist/requirements.txt  && pip install --no-cache-dir --no-deps /tmp/dist/*.whl  && rm -rf /tmp/dist  && python -m pip uninstall -y pip

USER nonroot
# Run the CLI by default; arguments passed to `docker run` are forwarded.
ENTRYPOINT ["nexus-azure-migrate"]
