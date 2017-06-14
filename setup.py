from setuptools import setup, find_packages

import osgeo_importer.version

with open('README.md') as f:
    readme = f.read()

setup(
    name='django-osgeo-importer',
    version=osgeo_importer.version.get_version(),
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
    include_package_data=True,
    zip_safe=False,
)
