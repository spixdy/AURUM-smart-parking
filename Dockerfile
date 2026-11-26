FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY aurum aurum
COPY data data
COPY .streamlit .streamlit
COPY streamlit_app.py .
# bake the trained model into the image so first start is instant
RUN python -m aurum.model train

RUN useradd --create-home app && chown -R app:app /app
USER app

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health')"
# default: dashboard. Override with `python -m aurum.ingest` or `python -m aurum.simulator`.
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
