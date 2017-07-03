#!/bin/bash
echo "Redirecting container's 'localhost' to container host."

# Since this docker container is for a developer using a virtualenv on the host, this is a bit of
#   a hack so when a database with host 'localhost' in the project settings file
#   has its config passed to geoserver it will reference the host the developer expects.
HOST_IP=`ip route | grep default | awk '{ printf "%s",$3 }'`

cat /etc/hosts | sed "s/127.0.0.1/$HOST_IP/" > /tmp/etc_hosts
cp /tmp/etc_hosts /etc/hosts

/opt/geoserver/bin/startup.sh
