__all__ = [
    "__title__", "__summary__", "__uri__", "__version__", "__author__",
    "__email__", "__license__", "__copyright__",
]

__title__ = "ztv"
__summary__ = "Simple python image viewer, largely intended for astronomical applications"
__uri__ = "https://github.com/henryroe/ztv"

#   https://python-packaging-user-guide.readthedocs.org/en/latest/distributing.html#version
# intended numbering convention during a release cycle is, e.g.  [decided this after some fumbling]
#   0.1.1.dev      # during development of 0.1.1
#   0.1.1.rc2      # shouldn't really be using much as I think I now have github/pypi figured out a little better
#   0.1.1          # released
#   0.1.1-3        # quick bug fixes
__version__ = "0.1.0.post1"

__author__ = "Henry Roe"
__email__ = "hroe@hroe.me"

__license__ = "MIT License"
__copyright__ = "2015 %s" % __author__
