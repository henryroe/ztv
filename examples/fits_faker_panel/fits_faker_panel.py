import wx
from wx.lib.pubsub import Publisher
import numpy as np
from astropy.io import fits
import time
import datetime
import os.path
import os
import glob
import psutil
import threading


class FakeFitsMaker(threading.Thread):
    def __init__(self, ztvframe_pid=None):
        self.ztvframe_pid = ztvframe_pid  # will kill self if this pid no longer alive
        self.nx = 512
        self.ny = 512
        self.flat_field_pixel_to_pixel_fractional_1sigma = 0.1
        self.sky_pattern_mean_cts = 9000.
        self.sky_pattern_row_to_row_variation_1sigma_cts = 2000.
        self.seeing_gauss_width = 2.0  # not fwhm....being lazy
        self.n_bkgd_stars = 50
        
        self.delay_between_frames_sec = 1.0
        
        self.data_dir = '/tmp/'
        self.files_to_delete = []
        self.frame_number = 1
        
        self.set_up_bkgd_stars()
        self.make_sky_frame()
        self.make_flat_frame()
        self.write_to_fits_file(self.sky_frame, 'sky_frame.fits')
        self.write_to_fits_file(self.flat_frame, 'flat_frame.fits')
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        keep_running = True
        while keep_running:
            im = self.make_data_frame()
            self.write_to_fits_file(im, 'current.fits')
            self.write_to_fits_file(im, 'n{:04d}.fits'.format(self.frame_number))
            self.frame_number += 1
            time.sleep(self.delay_between_frames_sec)
            if not psutil.pid_exists(self.ztvframe_pid):
                keep_running = False
        self.delete_files()
    
    def set_up_bkgd_stars(self):
        flux_lognormal_sigma = 1.0
        flux_multiplier = 2500.
        self.bkgd_stars = {}
        self.bkgd_stars['x'] = np.random.uniform(low=0., high=self.nx - 1, size=self.n_bkgd_stars)
        self.bkgd_stars['y'] = np.random.uniform(low=0., high=self.ny - 1, size=self.n_bkgd_stars)
        self.bkgd_stars['peak_cts'] = flux_multiplier * np.random.lognormal(sigma=flux_lognormal_sigma, 
                                                                            size=self.n_bkgd_stars)
        self.bkgd_stars_frame = np.zeros([self.ny, self.nx])
        for i in np.arange(self.n_bkgd_stars):
            dxs = np.outer(np.ones(self.ny), np.arange(self.nx)) - self.bkgd_stars['x'][i]
            dys = np.outer(np.arange(self.ny), np.ones(self.nx)) - self.bkgd_stars['y'][i]
            self.bkgd_stars_frame += (self.bkgd_stars['peak_cts'][i] *
                                      np.exp(-((dxs)**2 + (dys)**2) / (2. * self.seeing_gauss_width**2)))

    def calc_one_sky(self):
        return np.array([np.random.poisson(a, size=self.nx) for a in self.sky_frame_row_baseline])
        
    def make_sky_frame(self):
        self.sky_frame_row_baseline = np.random.normal(loc=self.sky_pattern_mean_cts, scale=
                                                       self.sky_pattern_row_to_row_variation_1sigma_cts,
                                                       size=self.ny)
        self.sky_frame_row_baseline[self.sky_frame_row_baseline <= 0] = 0.
        self.sky_frame = self.calc_one_sky()
    
    def make_flat_frame(self):
        self.flat_frame = np.random.normal(loc=1.0, scale=self.flat_field_pixel_to_pixel_fractional_1sigma, 
                                           size=[self.ny, self.nx])
                                           
    def make_data_frame(self):
        im = (self.bkgd_stars_frame + self.calc_one_sky()) / self.flat_frame
        for x in np.arange(self.nx):  # has to be a better way than this dumb/slow loop
            for y in np.arange(self.ny):
                im[y, x] = np.random.poisson(im[y, x])
        return im

    def delete_files(self):
        for curfile in self.files_to_delete:
            try:
                os.remove(os.path.join(self.data_dir, curfile))
            except OSError:  # ignore error if file doesn't exist
                pass

    def write_to_fits_file(self, im, filename):
        hdu = fits.PrimaryHDU(im)
        hdu.writeto(os.path.join(self.data_dir, filename), clobber=True)
        if filename not in self.files_to_delete:
            self.files_to_delete.append(filename)
            
            
            
class FitsFakerPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)

        static_text = wx.StaticText(self, wx.ID_ANY, u"Fits Faker", wx.DefaultPosition, wx.DefaultSize, 
                                    wx.ALIGN_CENTER )
        static_text.Wrap( -1 )
        v_sizer1.Add(static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)

        static_text = wx.StaticText(self, wx.ID_ANY, u"Example of a panel added-on to ztv", wx.DefaultPosition, 
                                    wx.DefaultSize, wx.ALIGN_CENTER )
        static_text.Wrap( -1 )
        v_sizer1.Add(static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)

#         self.clear_button = wx.Button(self, wx.ID_ANY, u"Clear", wx.DefaultPosition, wx.DefaultSize, 0)
#         h_sizer2.Add(self.clear_button, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 2)
#         self.clear_button.Bind(wx.EVT_BUTTON, self.on_clear_button)

        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)
        self.SetSizer(v_sizer1)


if __name__ == '__main__':
    import ztv
    z = ztv.ZTV()
