"""
rsCollectors -- scripts to retrieve remote sensing data at AVO

"""

from setuptools import setup, find_packages
from rsCollectors import __version__

DOCSTRING = __doc__.split("\n")

setup(
    name="rsCollectors",
    version=__version__,
    author="Tom Parker",
    author_email="tparker@usgs.gov",
    description=(DOCSTRING[1]),
    license="CC0",
    url="http://github.com/tparker-usgs/rsCollectors",
    packages=find_packages(),
    long_description='\n'.join(DOCSTRING[3:]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Software Development :: Libraries",
        "License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication",
    ],
    dependency_links=[
        'https://github.com/tparker-usgs/py-single/tarball/py3#egg=single-1.0.0'
    ],
    install_requires=[
        'pycurl',
        'h5py'
    ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    scripts=['bin/singleTimeout.sh'],
    entry_points={
        'console_scripts': [
            'mirror_gina = rsCollectors.mirror_gina:main'
        ]
    }
)
