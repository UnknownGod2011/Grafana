FROM python:3.12-slim
WORKDIR /app
COPY simulator.py /app/simulator.py
EXPOSE 9108
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/simulator.py"]
