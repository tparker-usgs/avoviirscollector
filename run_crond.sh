#!/bin/bash

# prepend application environment variables to crontab
env | grep -v PATH | cat - /tmp/cron-collectors > /etc/cron.d/cron-collectors

/usr/sbin/cron -f 
