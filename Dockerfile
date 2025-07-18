FROM python:3.13

ENV PYTHONUNBUFFERED=1

# Arbeitsverzeichnis
WORKDIR /app

# Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bot-Code kopieren
COPY . .

CMD ["python", "main.py"]