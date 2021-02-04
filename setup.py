import os
from setuptools import find_packages, setup
from glob import glob
from os.path import basename
from os.path import splitext

reqs_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')

with open(reqs_path, 'r') as req_file:
    dependencies = req_file.readlines()

setup(
    name='lpshipit',
    version='0.4.6',
    install_requires=dependencies,
    url='',
    license='',
    author='philroche',
    author_email='phil.roche@canonical.com',
    description='Helpful utility for merging launchpad MPs'
                ' (only works for git repos)',
    packages=find_packages(),
    package_dir={'': '.'},
    py_modules=[splitext(basename(path))[0] for path in glob('*.py')],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'lpshipit = lpshipit:lpshipit',
            'lpmpmessage = lpmpmessage:lpmpmessage',
            'lpmptox = lpmptox:lpmptox',
        ],
    },
)
