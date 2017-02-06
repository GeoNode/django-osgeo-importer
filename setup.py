from setuptools import setup, find_packages

import osgeo_importer

with open('README.md') as f:
    readme = f.read()

setup(
    name='django-osgeo-importer',
    version='.'.join(str(i) for i in osgeo_importer.__version__),
    description='django-osgeo-importer is a reusable Django application for '
                'inspecting geospatial data using GDAL/OGR and importing the '
                'data into an application.',
    long_description=readme,
    author='Tyler Garner',
    author_email='garnertb@prominentedge.com',
    maintainer='django-osgeo-importer contributors',
    url='https://github.com/GeoNode/django-osgeo-importer',
    # see MANIFEST for packaging exclusions
    packages=find_packages('.'),
    license='GPLv3+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later'
        ' (GPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Framework :: Django :: 1.8',
    ],
    install_requires=[
        'django-tastypie>=0.12.2,<0.14',
        'python-dateutil>=2.5.3,<2.7',
        'numpy>=1.11.2,<1.12',
        'geonode>=2.5.9,<2.6',
        'Django>=1.8,<1.9',
    ],
    include_package_data=True,
    zip_safe=False,
)
