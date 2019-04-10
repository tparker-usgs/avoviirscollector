FROM tparkerusgs/avopytroll:release-1.4.0

WORKDIR /app
COPY segment_gatherer.ini .
COPY trollstalker.ini .

WORKDIR /app/avoviirscollector
COPY cron-viirscollector .
COPY mirrorGina.yaml .
COPY setup.cfg .
COPY setup.py .
COPY avoviirscollector avoviirscollector
RUN python setup.py install

COPY supervisord.conf /etc/supervisor/supervisord.conf

RUN pip freeze > requirements.txt
CMD ["supervisord"]
