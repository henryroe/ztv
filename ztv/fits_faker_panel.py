import numpy as np
from astropy.io import fits
import time
import datetime
import os.path
import glob


class FakeFitsMaker():
    def __init__(self):
        self.nx = 512
        self.ny = 512
        self.flat_field_pixel_to_pixel_fractional_1sigma = 0.1
        self.sky_pattern_mean_cts = 9000.
        self.sky_pattern_row_to_row_variation_1sigma_cts = 2000.
        self.seeing_gauss_width = 2.0  # not fwhm....being lazy
        self.n_bkgd_stars = 50
        
        self.set_up_bkgd_stars()
        self.make_sky_frame()
        self.make_flat_frame()
        
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

        