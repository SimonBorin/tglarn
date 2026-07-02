FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libncurses-dev \
        make \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE.txt ./
COPY vendor/relarn ./vendor/relarn
COPY bot ./bot
COPY game ./game

RUN rm -f vendor/relarn/src/relarn.bin vendor/relarn/src/deps.mk vendor/relarn/src/*.o vendor/relarn/src/fov/*.o \
    && RELARN_SYS="$(case "$(uname -m)" in aarch64|arm64|arm*) echo linux-arm ;; x86_64|amd64|i?86) echo linux-x86 ;; *) vendor/relarn/build_helpers/platform-id.sh ;; esac)" \
    && make -C vendor/relarn/src RELEASE=y SYS="$RELARN_SYS" \
    && mkdir -p \
        /opt/relarn/lib/relarn \
        /opt/relarn/share/relarn/lib \
        /opt/relarn/var/relarn \
    && cp vendor/relarn/src/relarn.bin /opt/relarn/lib/relarn/relarn.bin \
    && cp vendor/relarn/data/Uhelp /opt/relarn/share/relarn/lib/Uhelp \
    && cp vendor/relarn/data/Umaps /opt/relarn/share/relarn/lib/Umaps \
    && cp vendor/relarn/data/Ufortune /opt/relarn/share/relarn/lib/Ufortune \
    && cp vendor/relarn/data/Uintro /opt/relarn/share/relarn/lib/Uintro \
    && cp vendor/relarn/data/Ujunkmail /opt/relarn/share/relarn/lib/Ujunkmail \
    && cp vendor/relarn/data/relarnrc.sample /opt/relarn/share/relarn/lib/relarnrc.sample \
    && cp -R vendor/relarn/data/fonts /opt/relarn/share/relarn/lib/fonts \
    && touch /opt/relarn/var/relarn/Relarn-scoreboard \
    && chmod a+rw /opt/relarn/var/relarn/Relarn-scoreboard \
    && python -m pip wheel --wheel-dir /tmp/wheels .

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RELARN_BINARY_PATH=/opt/relarn/lib/relarn/relarn.bin \
    RELARN_INSTALL_ROOT=/opt/relarn

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libncurses6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/relarn /opt/relarn
COPY --from=builder /tmp/wheels /tmp/wheels

RUN python -m pip install --no-index --find-links /tmp/wheels tglarn \
    && rm -rf /tmp/wheels

USER appuser

CMD ["python", "-m", "tglarn_bot.main"]
