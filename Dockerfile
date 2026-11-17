FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir pika==1.3.2 tzdata
COPY broker.py acompanhamento.py notificacoes.py ./
ENV PYTHONUNBUFFERED=1
