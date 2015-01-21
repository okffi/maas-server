#!/bin/bash

/etc/init.d/postgresql start
sudo -u postgres python /maas/server/server2.py $1