# AWS's Lambda base image. It includes the Runtime Interface Emulator,
# so the same image runs locally (docker compose) and in Lambda.
FROM public.ecr.aws/lambda/python:3.13 AS runtime

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target ${LAMBDA_TASK_ROOT}

COPY *.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.lambda_handler"]


# Test image: runtime plus test tools. Never deployed (build Lambda with --target runtime).
# backend/ is mounted at /backend by docker compose, so edits don't need a rebuild.
FROM runtime AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

ENV PYTHONPATH=/backend/rsvp:${LAMBDA_TASK_ROOT}
WORKDIR /backend
ENTRYPOINT ["python", "-m", "pytest"]
