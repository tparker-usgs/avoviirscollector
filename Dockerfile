FROM tparkerusgs/avopytroll:release-1.4.0

WORKDIR /app
COPY segment_gatherer.ini .
COPY trollstalker.ini .

WORKDIR /app/rscollectors
COPY cron-collectors .
COPY setup.cfg .
COPY setup.py .
COPY rscollectors rscollectors
RUN python setup.py install

COPY supervisord.conf /etc/supervisor/supervisord.conf

CMD ["sh","-c","configupdater && supervisord"]
