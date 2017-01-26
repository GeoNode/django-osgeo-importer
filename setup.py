from setuptools import setup, find_packages

import osgeo_importer

with open('README.md') as f:
    readme = f.read()

setup(
    name='django-osgeo-importer',
    version='.'.join(str(i) for i in osgeo_importer.__version__),
    description='django-osgeo-importer is a reusable Django application for inspecting geospatial data using GDAL/OGR and importing the data into an application.',
    long_description=readme,
    author='Tyler Garner',
    author_email='garnertb@prominentedge.com',
    maintainer='django-osgeo-importer contributors',
    url='https://github.com/GeoNode/django-osgeo-importer',
    # osgeo_importer_prj is only used for development & testing
    packages=('osgeo_importer',),
    package_data={
        'osgeo_importer': [
            'locale/*/LC_MESSAGES/*',
            'templates/osgeo_importer/*',
            # Include all of the static files except for the 'test' subdir.
            'static/osgeo_importer/css/*',
            'static/osgeo_importer/factories.js',
            'static/osgeo_importer/importer.js',
            'static/osgeo_importer/karma.conf.js',
            'static/osgeo_importer/package.json',
            'static/osgeo_importer/privacy.png',
            'static/osgeo_importer/time.png',
            'static/osgeo_importer/edit.png',
            'static/osgeo_importer/img/*',
            'static/osgeo_importer/js/*',
            'static/osgeo_importer/Makefile',
            'static/osgeo_importer/partials/*',
        ],
    },
    license='GPLv3+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Framework :: Django :: 1.8',
    ],
    install_requires=[
        'django-tastypie==0.12.2',
        'python-dateutil==2.5.3',
        'numpy==1.11.2',
        'geonode==2.5.9',
        'Django==1.8',
    ],
    include_package_data=True,
    zip_safe=False,
)
