FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt ./
RUN pip install --user -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app/venv/lib/python3.12/site-packages:$PYTHONPATH
ENV PATH=/app/venv/bin:$PATH

COPY --from=builder /root/.local /app/venv
COPY *.py ./
COPY requirements.txt ./

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
