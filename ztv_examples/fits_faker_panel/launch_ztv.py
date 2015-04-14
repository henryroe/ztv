from __future__ import absolute_import
from ztv import ZTV

# intended to be run with, e.g.:
#     ipython
#     run launch_ztv.py
# or
#     ipython
#     from ztv_examples.fits_faker_panel.launch_ztv import launch_ztv
#     z = launch_ztv()


def launch_ztv():
    return ZTV(control_panels_module_path='ztv_examples.fits_faker_panel.control_panels')

if __name__ == '__main__':
    z = launch_ztv()