FROM python:3.10

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && pip install -r requirements.txt

ENV PORT 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "--workers=1", "--threads=8", "--timeout=0", "main:app"]
