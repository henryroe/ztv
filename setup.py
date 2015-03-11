from setuptools import setup, find_packages  # Always prefer setuptools over distutils
from codecs import open  # To use a consistent encoding
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ztv',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.1.0dev1',

    description='Simple python image viewer, largely intended for astronomical applications',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/henryroe/ztv',

    # Author details
    author='Henry Roe',
    author_email='hroe@hroe.me',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #     Development Status :: 1 - Planning
        #     Development Status :: 2 - Pre-Alpha
        #     Development Status :: 3 - Alpha
        #     Development Status :: 4 - Beta
        #     Development Status :: 5 - Production/Stable
        #     Development Status :: 6 - Mature
        #     Development Status :: 7 - Inactive
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',
        'Topic :: Multimedia :: Graphics :: Viewers',
        'Topic :: Scientific/Engineering :: Astronomy',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
#         'Programming Language :: Python :: 2.6',  # no reason to believe won't work on 2.6, but am not testing
        'Programming Language :: Python :: 2.7',
#  Intention is to write to v3 compatibility and eventually test, but am not doing that as of now (2015-03-06)
#         'Programming Language :: Python :: 3',
#         'Programming Language :: Python :: 3.2',
#         'Programming Language :: Python :: 3.3',
#         'Programming Language :: Python :: 3.4',
    ],

    # What does your project relate to?
    keywords='astronomy image viewer fits',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),

    # List run-time dependencies here.  These will be installed by pip when your
    # project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['stompy', 'numpy>=1.8.1'],

    # List additional groups of dependencies here (e.g. development dependencies).
    # You can install these using the following syntax, for example:
    # $ pip install -e .[dev,test]
# 2015-03-06: haven't considered if we need/want any of these
#     extras_require = {
#         'dev': ['check-manifest'],
#         'test': ['coverage'],
#     },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
# 2015-03-06: haven't considered if we need/want any of these
#     package_data={
#         'sample': ['package_data.dat'],
#     },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages.
    # see http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
# 2015-03-06: haven't considered if we need/want any of these
#     data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
# 2015-03-06: haven't considered if we need/want any of these
#     entry_points={
#         'console_scripts': [
#             'sample=sample:main',
#         ],
#     },
)