FROM python:3.12-slim
WORKDIR /app
COPY simulator.py /app/simulator.py
COPY watchdog_metrics_fixture.py /app/watchdog_metrics_fixture.py
EXPOSE 9108 9111
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/simulator.py"]
