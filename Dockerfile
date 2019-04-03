FROM tparkerusgs/avopytroll:2.3.0

WORKDIR /app
COPY cron-collectors .
COPY setup.cfg .
COPY setup.py .
COPY rscollectors rscollectors
RUN python setup.py install

COPY supervisord.conf /etc/supervisor/supervisord.conf

CMD ["/usr/local/bin/supervisord"]
