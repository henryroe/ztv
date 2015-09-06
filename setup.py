from setuptools import setup, find_packages  # Always prefer setuptools over distutils
from codecs import open  # To use a consistent encoding
import os

base_dir = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(base_dir, "ztv", "__about__.py")) as f:
    exec(f.read(), about)

# Get the long description from the relevant file, converting from md to rst if possible
with open(os.path.join(base_dir, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()
try:
    from pypandoc import convert
    long_description = convert('README.md', 'rst', format='md')
    # also, convert screen shot links to point to github
    import re
    rep = re.compile('screenshots/(.*).png')
    long_description = rep.sub(r'https://raw.githubusercontent.com/henryroe/ztv/master/screenshots/\1.png', long_description)
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")


setup(
    name=about["__title__"],

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=about["__version__"],

    description=about["__summary__"],
    long_description=long_description,

    # The project's main homepage.
    url=about["__uri__"],

    # Author details
    author=about["__author__"],
    author_email=about["__email__"],

    # Choose your license
    license=about["__license__"],

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
        'Development Status :: 4 - Beta',

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
    # Note: stompy is needed for ActiveMQ integration, but can be safely ignored unless needed
    # Note: astropy will require numpy, so no need to specify here (had been: 'numpy>=1.8.1')
    # Note: matplotlib version requirement could maybe be even earlier as we're not doing anything bleeding edge.
    # Note: scipy not required, but highly recommended and some functionality may be lost without it. 
    #       (at time of writing, v0.1.0, you lost some of the analysis in the phot_panel.py)
    install_requires=['astropy>=1.0.0', 'wxPython>=3.0', 'matplotlib>=1.3', 'psutil>=2.0', 'astropy_helpers>=1.0.0'],

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
