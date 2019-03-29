#!/bin/bash 

WHO=tparker@usgs.gov
VERBOSE=0
while getopts t:c:f:v opt; do
    case $opt in
        t)
            TIMEOUT=$OPTARG
            ;;
        c)
            COMMAND=$OPTARG
            ;;
        f)
            LOCKFILE=$OPTARG
            ;;
        v)
            VERBOSE=1
    esac
done

if [  "X$TIMEOUT" = X -o "X$COMMAND" = X ]; then
    echo "Usage: $0 -t <timeout in seconds> -c <command> [ -f <lockfile> ]"
    exit 1
fi

if [ X$LOCKFILE != X ]; then
    LOCKFILEARG="-f $LOCKFILE"
fi

OUT=`single.py --status $LOCKFILEARG -c $COMMAND`

# not locked, exit
if [ $? = 0 ]; then
    if [ $VERBOSE = 1 ]; then
        echo "Process not running"
    fi
    exit 0
fi

PID=`echo $OUT | awk '{print$3}' | sed -e 's/:$//'`
TIME=`ps -p $PID -o etimes= | xargs`

# not stale exit
if (( $TIME < $TIMEOUT )) ; then
    if [ $VERBOSE = 1 ]; then
        echo "Process not stale. ($TIME < $TIMEOUT)"
    fi
    exit 0
fi

OUT_MSG="Command running too long, killing it. ($TIME > $TIMEOUT)\n"
OUT_MSG+=`ps -fp $PID | sed -e 's/$/\\n/'`
kill -9 $PID

if [ $VERBOSE = 1 ]; then
    echo -e $OUT_MSG
fi
echo -e $OUT_MSG | mailx -s "stale proc: $COMMAND" $WHO
