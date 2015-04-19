import numpy as np
from astropy.io import fits
import time
import os.path
import os
import psutil
import threading


class FakeFitsMaker(threading.Thread):
    def __init__(self, ztv_frame_pid=None):
        self.ztv_frame_pid = ztv_frame_pid  # will kill self if this pid no longer alive
        self.nx = 512
        self.ny = 512
        self.flat_field_pixel_to_pixel_fractional_1sigma = 0.15
        self.flat_field_num_dust_donuts = 30
        self.flat_field_dust_donuts_radius_range = [20, 50]
        self.flat_field_dust_donuts_width_range = [10, 15]
        self.flat_field_dust_donuts_peak_range = [0.5, 0.8]
        self.sky_pattern_mean_cts = 9000.
        self.sky_pattern_row_to_row_variation_1sigma_cts = 2000.
        self.saturation_cts = 2**16
        self.seeing_gauss_width = 2.0  # not fwhm....being lazy
        self.n_bkgd_stars = 50
        
        self.n_moving_objects = 10
        self.moving_objects = []
        
        self.delay_between_frames_sec = 2.0
        
        self.data_dir = '/tmp/'
        self.files_to_delete = []
        self.frame_number = 1
        
        self.set_up_bkgd_stars()
        self.make_flat_frame()
        self.make_sky_frame()
        self.write_to_fits_file(self.sky_frame, 'sky_frame.fits')
        self.write_to_fits_file(self.flat_frame, 'flat_frame.fits')
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        self.keep_running = True
        while self.keep_running:
            im = self.make_data_frame()
            self.write_to_fits_file(im, 'current.fits')
            self.write_to_fits_file(im, 'n{:04d}.fits'.format(self.frame_number))
            self.frame_number += 1
            time.sleep(self.delay_between_frames_sec)
            if not psutil.pid_exists(self.ztv_frame_pid):
                self.keep_running = False
        self.delete_files()
    
    def set_up_bkgd_stars(self):
        flux_lognormal_sigma = 1.0
        flux_multiplier = 7000.
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

    def new_moving_object(self):
        flux_lognormal_sigma = 1.0
        flux_multiplier = 10000.
        new_object = {'peak_cts': flux_multiplier * np.random.lognormal(sigma=flux_lognormal_sigma)}
        new_object['x'] = 0.
        new_object['y'] = np.random.uniform(low=1., high=self.ny - 2)
        new_object['dx'] = np.random.normal(loc=20, scale=15.)
        new_object['dy'] = np.random.normal(loc=0., scale=10.)
        return new_object
        
    def advance_moving_objects(self):
        remaining_moving_objects = []
        for cur_moving_object in self.moving_objects:
            cur_moving_object['x'] += cur_moving_object['dx']
            cur_moving_object['y'] += cur_moving_object['dy']
            if ((cur_moving_object['x'] >= 0.) and (cur_moving_object['y'] >= 0.) and
                (cur_moving_object['x'] < self.nx) and (cur_moving_object['y'] < self.ny)):
                remaining_moving_objects.append(cur_moving_object)
        self.moving_objects = remaining_moving_objects

    def calc_one_sky(self):
        return np.array([np.random.poisson(a, size=self.nx) for a in self.sky_frame_row_baseline])
        
    def make_sky_frame(self):
        self.sky_frame_row_baseline = np.random.normal(loc=self.sky_pattern_mean_cts, scale=
                                                       self.sky_pattern_row_to_row_variation_1sigma_cts,
                                                       size=self.ny)
        self.sky_frame_row_baseline[self.sky_frame_row_baseline <= 0] = 0.
        self.sky_frame = self.calc_one_sky() * self.flat_frame
    
    def make_flat_frame(self):
        flat = np.random.normal(loc=1.0, scale=self.flat_field_pixel_to_pixel_fractional_1sigma, size=[self.ny, self.nx])
        for i in range(self.flat_field_num_dust_donuts):
            x = np.random.uniform(0., self.nx)
            y = np.random.uniform(0., self.ny)
            radius = np.random.uniform(min(self.flat_field_dust_donuts_radius_range), 
                                       max(self.flat_field_dust_donuts_radius_range))
            width = np.random.uniform(min(self.flat_field_dust_donuts_width_range), 
                                      max(self.flat_field_dust_donuts_width_range))
            peak = np.random.uniform(min(self.flat_field_dust_donuts_peak_range),
                                     max(self.flat_field_dust_donuts_peak_range))
            xdist = np.outer(np.ones(flat.shape[0]), np.arange(flat.shape[1]) - x)
            ydist = np.outer(np.arange(flat.shape[0]) - y, np.ones(flat.shape[1]))
            dist = np.sqrt(xdist**2 + ydist**2)
            flat *= 1. - (1. - peak) * np.exp(-((dist - radius)**2) / (2. * width**2))
        self.flat_frame = flat
                                           
    def make_data_frame(self):
        im = self.bkgd_stars_frame.copy()
        self.advance_moving_objects()
        while len(self.moving_objects) < self.n_moving_objects:
            self.moving_objects.append(self.new_moving_object())
        for cur_moving_object in self.moving_objects:
            dxs = np.outer(np.ones(self.ny), np.arange(self.nx)) - cur_moving_object['x']
            dys = np.outer(np.arange(self.ny), np.ones(self.nx)) - cur_moving_object['y']
            im += (cur_moving_object['peak_cts'] * np.exp(-((dxs)**2 + (dys)**2) / (2. * self.seeing_gauss_width**2)))
        im = (im + self.calc_one_sky()) * self.flat_frame
        for x in np.arange(self.nx):  # has to be a better way than this dumb/slow loop
            for y in np.arange(self.ny):
                im[y, x] = min(np.random.poisson(max(im[y, x], 0)), self.saturation_cts)
        return im

    def delete_files(self):
        for curfile in self.files_to_delete:
            try:
                os.remove(os.path.join(self.data_dir, curfile))
            except OSError:  # ignore error if file doesn't exist
                pass

    def write_to_fits_file(self, im, filename):
        max_files_on_disk = 10  # play nice with space in people's /tmp/ dirs
        hdu = fits.PrimaryHDU(im)
        hdu.writeto(os.path.join(self.data_dir, filename), clobber=True)
        if filename not in self.files_to_delete:
            if filename.startswith('n'):
                self.files_to_delete = ([a for a in self.files_to_delete if a.startswith('n')] + 
                                        [filename] +
                                        [a for a in self.files_to_delete if not a.startswith('n')])
            else:
                self.files_to_delete.append(filename)
        while len(self.files_to_delete) > max_files_on_disk:
            os.remove(os.path.join(self.data_dir, self.files_to_delete.pop(0)))
            

if __name__ == '__main__':
    f = FakeFitsMaker()
    f.start()