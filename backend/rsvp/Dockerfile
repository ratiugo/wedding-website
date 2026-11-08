# AWS's Lambda base image. It includes the Runtime Interface Emulator,
# so the same image runs locally (docker compose) and in Lambda.
FROM public.ecr.aws/lambda/python:3.13 AS runtime

# Built from backend/ (see docker-compose.yml), so shared/ can be copied in too.
COPY rsvp/*.py shared/*.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.lambda_handler"]


# Test image: runtime plus test tools. Never deployed (build Lambda with --target runtime).
# backend/ is mounted at /backend by docker compose, so edits don't need a rebuild.
FROM runtime AS test

COPY rsvp/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

ENV PYTHONPATH=/backend/rsvp:/backend/shared:${LAMBDA_TASK_ROOT}
WORKDIR /backend
ENTRYPOINT ["python", "-m", "pytest"]
