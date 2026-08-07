# B2X sunucu imajı — hem API hem arka plan işçisi bu imajdan çalışır.
#
# Python sürümü yerel geliştirmeyle aynı tutulur (şartname Bölüm 3): 3.13.
# İmaj bind mount kullanmaz; kod imajın içine kopyalanır. Geliştirme sırasında
# hızlı döngü için backend Windows'ta native çalıştırılır, bu imaj teslim ve
# "tek komutla ayağa kalksın" içindir.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv/b2x

COPY pyproject.toml constraints.txt ./
COPY app ./app
COPY engine ./engine
COPY migrations ./migrations
COPY alembic.ini ./
COPY tests ./tests

# constraints.txt sürümleri sabitler, böylece imaj her derlemede aynı çıkar.
RUN pip install --no-cache-dir -c constraints.txt . \
    && useradd --create-home --uid 10001 b2x \
    && chown -R b2x:b2x /srv/b2x

# Uygulama root olarak çalışmaz.
USER b2x

# Varsayılan olarak API çalışır; worker servisi bu komutu compose'ta değiştirir.
# Adres ve port çalışma anında ortamdan okunur, imaja gömülmez.
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host \"${API_HOST:-0.0.0.0}\" --port \"${API_PORT:-${PORT:-8000}}\""]
