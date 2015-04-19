from __future__ import absolute_import
from ztv import ZTV
import wx
from wx.lib.pubsub import Publisher
import time

# intended to be run with, e.g.:
#     ipython
#     run launch_ztv.py
# or
#     ipython
#     from ztv_examples.fits_faker_panel.launch_ztv import launch_ztv
#     z = launch_ztv()

def launch_ztv():
    z = ZTV(control_panels_module_path='ztv_examples.fits_faker_panel.control_panels')
    z.start_fits_faker = lambda: z._send_to_ztv('fits-faker-start')
    z.stop_fits_faker = lambda: z._send_to_ztv('fits-faker-stop')
    z.control_panel('Faker')
    return z

if __name__ == '__main__':
    z = launch_ztv()