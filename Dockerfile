FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=src:.
ENV DBT_PROFILES_DIR=dbt

CMD ["bash", "-c", "python -m src.synth_corpus && python -m src.beam_ingest && python -m src.extractor && python -m src.warehouse --step staging && python -m src.entity_resolution && python -m src.warehouse --step marts && python -m src.evaluate && uvicorn src.api:app --host 0.0.0.0 --port 8120 & streamlit run src/dashboard.py --server.port 8501 --server.address 0.0.0.0"]
