#!/bin/sh

cd /data/omps/edr
wget -nd -r -l 1 --timeout 20 -nc -np --accept-regex='OMPS-NPP-TC_EDR_SO2NRT-*' -e robots=off http://dds.gina.alaska.edu/public/IPOPP/npp/omps/level2/
rm index.html
