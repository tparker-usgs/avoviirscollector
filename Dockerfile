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
ADD requirements.txt .
RUN pip install --default-timeout=60 --no-cache-dir -r requirements.txt # 1

ADD bin bin
# 1
ADD viirs viirs
ADD cron-collectors /tmp/cron-collectors
ADD run_crond.sh  .
RUN chmod 755 run_crond.sh

#CMD ["cron","-f"]
CMD ["/app/collectors/run_crond.sh"]
