from setuptools import setup

setup(
    name='maproulette',
    packages=['maproulette'],
    include_package_data=True,
    install_requires=[
        'Flask==0.12.0',
        'Flask-RESTful==0.3.5',
        'Flask-KVSession==0.6.2',
        'Flask-OAuthlib==0.9.3',
        'Flask-SQLAlchemy==2.1',
        'Flask-Runner==2.1.1',
        'Flask-Migrate==2.0.3',
        'GeoAlchemy2==0.4.0',
        'SQLAlchemy==1.1.5',
        'Shapely==1.5.17',
        'psycopg2==2.6.2',
        'simplejson==3.10.0',
        'geojson==1.3.4',
        'nose==1.3.7',
        'iso8601==0.1.11',
        'requests==2.13.0',
        'Fabric==1.13.1',
        'python-dateutil==2.6.0',
    ],
)
