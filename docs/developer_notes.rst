Developer Notes
===============

Getting Started
---------------
* Run tests in the vagrant vm:
    #. vagrant up
    #. vagrant ssh
    #. PYTHONPATH=/vagrant/src/geonode/ python /vagrant/manage.py test osgeo_importer

    In subsequent runs after restarting the vm, geoserver will likely not be running.
    Start it with::
    
        java -Xmx512m -XX:MaxPermSize=256m -Dorg.eclipse.jetty.server.webapp.parentLoaderPriority=true -jar gs/jetty-runner-8.1.8.v20121106.jar --path /geoserver gs/geoserver.war

    (taken from the end of scripts/before_script.sh)

* Run tests in a virtualenv on your machine (This does roughly the same thing as the VM setup):
    #. pip install -r requirements.txt
    #. pip install -r requirements.dev.txt
    #. sudo cp scripts/epsg_extra <your_virtualenv>/lib/python2.7/site-packages/pyproj/
    #. install gdal/ogr:
        For gdal/ogr python bindings, the easiest method is to install the system-level package
        and link to virtual env's site-packages.
            * Ubuntu: install system-level package python-gdal and link the following to site-packages/:
                *  /usr/lib/python2.7/dist-packages/GDAL-2.1.0.egg-info
                *  /usr/lib/python2.7/dist-packages/gdal.py
                *  /usr/lib/python2.7/dist-packages/gdalconst.py
                *  /usr/lib/python2.7/dist-packages/osr.py
                *  /usr/lib/python2.7/dist-packages/ogr.py
                *  /usr/lib/python2.7/dist-packages/gdalnumeric.py
                *  /usr/lib/python2.7/dist-packages/osgeo
    #. install postgres with postgis enabled:
        * Ubuntu:
            #. Add repo (swap "xenial" for "trusty" if that's what you're running)::
            
                add-apt-repository http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main
                
            #. Update::
            
                apt-get update
                
            #. Install::
            
                apt-get install postgresql-9.3-postgis-2.3
    #. create project's postgis geostore:
        #. sudo -u postgres psql -c "CREATE ROLE osgeo WITH SUPERUSER LOGIN PASSWORD 'osgeo';"
            * (Superuser is needed for postgis setup in database during automated testing)
        #. sudo -u postgres psql -c 'CREATE DATABASE osgeo_importer_test WITH OWNER osgeo;'
        #. sudo -u postgres psql -c 'GRANT ALL ON DATABASE osgeo_importer_test TO osgeo;'
        #. sudo -u postgres psql osgeo_importer_test -c 'CREATE EXTENSION postgis;'
    #. install geoserver (based on scripts/install.sh)::
    
        cd <your_geoserver_dir>
        wget -N http://central.maven.org/maven2/org/eclipse/jetty/jetty-runner/9.4.0.v20161208/jetty-runner-9.4.0.v20161208.jar
        wget -N http://ares.boundlessgeo.com/geoserver/2.9.2/geoserver-2.9.2-latest-war.zip
        wget -N http://build.geonode.org/geoserver/latest/geoserver.war

    (The travis/vagrant vm setup is using earlier versions, should that be upgraded or these downgraded?)

    #. get the test files from s3 bucket (based on scripts/install.sh)::
        
        aws --no-sign-request s3 sync s3://mapstory-data/importer-test-files/ importer-test-files
        
    #. Start PostgreSQL & Geoserver::

        sudo systemctl start postgresql
        cd <your_geoserver_dir>; java -Xmx512m -XX:MaxPermSize=256m -Dorg.eclipse.jetty.server.webapp.parentLoaderPriority=true -jar jetty-runner-9.4.0.v20161208.jar --path /geoserver geoserver.war
    
    #. Migrate your Django databases::
    
        python manage.py migrate
        
    #. Run your tests::
    
        cd <your_importer_dir>; python manage.py test osgeo_importer

Tips
----
* If you're running in the VM but testing using a browser on the host machine note that
  the geoserver requests will target the host machine rather than the vm.  Either
  start an instance on your host machine or forward port 8080 to the vm.

* If you're having trouble with a missing oath2_provider error on startup, these two dependencies
  will resolve the issue for xenial (16.04).  If you install them on 14.04 you will suffer
  migration conflicts::
    
    pip install django-oauth-toolkit
    pip install django-cors-headers

