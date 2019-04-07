avoviirscollector
============
[![Build Status](https://travis-ci.org/tparker-usgs/avoviirscollector.svg?branch=master)](https://travis-ci.org/tparker-usgs/avoviirscollector)
[![Code Climate](https://codeclimate.com/github/tparker-usgs/avoviirscollector/badges/gpa.svg)](https://codeclimate.com/github/tparker-usgs/avoviirscollector)

Docker container to collect viirs data at AVO

**I'm still under development. Some of what you see below is outdated, while other parts may be aspirational. Talk to Tom 
before doing anything that matters.**

Overview
--------
I gather VIIRS data files and present an event stream of products to produce. 

I peridically run scripts to retrieve files from remote sources and publish collections using the 
[posttroll](https://github.com/pytroll/posttroll) messaging system.

Daemons:
  * supervisord - launches all other deamons and keeps them running
  * supercronic - a cron daemon which Launches periodic tasks
  * nameserver - keeps track of active publishers on the internal messaging system and tells listeners where to find 
                 active publishers.
  * trollstalker - watches local directories for new files and publishes files as they're recieved
  * segment_gatherer - listens to trollstalker and assembles files into a complete granule
  * msg_broker - collects messages from segment_gatherer and provides tasks to [viirsprocessors](https://github.com/tparker-usgs/avoviirsprocessor)
  
Cron taks:
  * mirror_gina - searches GINA for recent images and retrieves any found
  * cleanup - remove old images

Filesystems
-----------
All log files and data I create are written to /rsdata in the container, which I expect that to be provided as a docker
volume. Look at the docker run command or docker-compose file for it's true locatiom.

supervisord
-----------
Launch deamons and keep them running. Additional info on supervisord is available at <http://supervisord.org/>.

**logs**

supervisord writes its log file to /rsdata/log/avoviirscollector/supervisord.log. In there will be details about when deamons
are launched and when they die. If all is going well, it'll be a short uninteresting log file.

Each deamon launched by supervisord will have two log files, capturing STDOUT and STDERR from its process. These logs 
are placed in /rsdata/log/avoviirscollector with unpredictable, but easily identifiable, names.

**quirks**

  * supervisord log file perms are super restrictive and do not honor the umask. Watching 
    [issue #123](https://github.com/Supervisor/supervisor/issues/123) for resolution.

supercronic
-----------
Launch periodic tasks. Additional info on supercronic is available at <https://github.com/aptible/supercronic>

**logs**

Supercronic doesn't write any task-specific log files. STDOUT and STDERR of tasks launched by supercronic are logged in
the supercronic log files created by supervisord.

nameserver
----------
nameserver is part of the PyTroll posttroll project. Additional info on posttrol is available at
<https://github.com/pytroll/posttroll>.

The posttroll nameserver keeps track of topics learned from messages broadcasted by publishers and responds to queries
from listeners looking for a topic. It has no configuration file and rarely causes trouble.

trollstalker
------------
trollstalker is part of the PyTroll pytroll-collectors project. Additional info on pytroll-collectors is available at
<https://github.com/pytroll/pytroll-collectors>.

Uses inotify to watch for new files and publishes messages to start processing.

**logs**

trollstalker doesn't write any logs beyond the two created by supervisord. The STDERR log will note every file found by
trollstalker.

**quirks**

  * Because trollstalker uses inotify, it must be run close to whatever retrieves files when watching a directory on a
    NFS share. The kernel won't know about files that are created outside of it's control.

segment_gatherer
----------------
segment_gatherer is part of the PyTroll pytroll-collectors project. Additional info on pytroll-collectors is available
at <https://github.com/pytroll/pytroll-collectors>.

Listens to messages published by trollstalker and publishes a message whenever a complete granule is ready to be
processed. 

**quirks**

  * segment_gatherer expects to find a nameserver on the localhost.

mirror_gina
-----------
Searches GINA NRT for recent files and retrieves any found.

**logs**

mirror_gina doesn't write its own logfiles. look for output in the cupercronic logs.

 
cleanup
-------

**environemnt variables**
  * _DAYS_RETENTION_ Maximum file retention in $RSPROCESSING_BASE

old notes
=========
Ignore stuff under here. It's just waiting to be worked into the above text.

Environment variables
---------------------
I look to the environment for my bootstrap config. I require three enironrment variables.
  * _RSPROCESSING_BASE_ local filesystem path of my working directory

I will email logged errors if desired.
  * _MAILHOST_ Who can forward mail for me?
  * _LOG_SENDER_ From: address
  * _LOG_RECIPIENT_ To: address

Optionally, I'll cleanup downloaded files after some number of days.
  * _DAYS_RETENTION_ Maximum file retention in $RSPROCESSING_BASE

docker-compose
--------------
Here is an example service stanza for use with docker-compose.

    collectors:
      image: "tparkerusgs/avoviirscollector:release-2.0.2"
      user: "2001"
      environment:
        - RSPROCESSING_BASE=/rsdata
        - MIRROR_GINA_CONFIG=/tmp/mirrorGina.yaml
        - DAYS_RETENTION=7 
        - PYTHONUNBUFFERED=1
        - MAILHOST=smtp.usgs.gov
        - LOG_SENDER=avoauto@usgs.gov
        - LOG_RECIPIENT=tparker@usgs.gov
        - CU_CONFIG_URL=https://avomon01.wr.usgs.gov/svn/docker/rsprocessing/configupdater-collectors.yaml
        - CU_CONTEXT_NAME=collectors
        - CU_USER=user
        - CU_PASSWORD=password
      restart: always
      logging:
        driver: json-file
        options:
          max-size: 10m
      volumes:
        - type: volume
          source: rsdata
          target: /rsdata
          volume:
            nocopy: true
