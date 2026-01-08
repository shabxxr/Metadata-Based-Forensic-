FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# ---- Install ONLY available SAFE tools ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    exiftool \
    exiv2 \
    imagemagick \
    binwalk \
    ffmpeg \
    mediainfo \
    binutils \
    file \
    poppler-utils \
    qpdf \
    mupdf-tools \
    docx2txt \
    tshark \
    && rm -rf /var/lib/apt/lists/*

# ---- Python dependencies ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy app ----
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
