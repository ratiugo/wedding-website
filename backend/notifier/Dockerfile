# Same layout as rsvp/Dockerfile: `runtime` is the Lambda image, `test` adds dev tools.
FROM public.ecr.aws/lambda/python:3.13 AS runtime

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target ${LAMBDA_TASK_ROOT}

COPY *.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.lambda_handler"]


# backend/ is mounted at /backend by docker compose, so edits don't need a rebuild.
FROM runtime AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

ENV PYTHONPATH=/backend/notifier:${LAMBDA_TASK_ROOT}
WORKDIR /backend
ENTRYPOINT ["python", "-m", "pytest"]
