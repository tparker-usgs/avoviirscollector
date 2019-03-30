# can't use onbuild due to SSL visibility
FROM python:3.7

# install supercronic
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.1.8/supercronic-linux-amd64 \
    SUPERCRONIC=supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=be43e64c45acd6ec4fce5831e03759c89676a0ea

RUN curl -fsSLO "$SUPERCRONIC_URL" \
 && echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - \
 && chmod +x "$SUPERCRONIC" \
 && mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" \
 && ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic

WORKDIR /app/collectors
COPY cron-collectors .
COPY setup.cfg .
COPY setup.py .
COPY rsCollectors rsCollectors
RUN python setup.py install

# not using requirements.txt because order matters
RUN pip install --default-timeout=60 Cython
RUN pip install --default-timeout=60 single

CMD ["supercronic", "cron-collectors"]
