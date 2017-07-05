# Provides this geoserver image with 'localhost' remapped to the host machine so db requests are made to host port 5432.
FROM winsent/geoserver:2.11.0

ENV TERM=linux

COPY startup_extra.sh /opt/geoserver/bin/startup_extra.sh
RUN chmod a+x /opt/geoserver/bin/startup_extra.sh
CMD ["/opt/geoserver/bin/startup_extra.sh"]
