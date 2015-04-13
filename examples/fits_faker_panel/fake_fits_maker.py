import numpy as np
from astropy.io import fits
import time
import os.path
import glob
import stomp
import cPickle as pickle
import sys

import PIL
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw

# TODO:  move output datadir to /tmp
# TODO:  figure out how to package simple_image.fits in with distribution and find it from this code

class FakeFitsMaker():
    def __init__(self):
        datadir = '/Users/hroe/Dropbox/py/ztv/ztv/test_data/'
        files_to_delete = glob.glob(datadir + 'n*fits')
        for curfile in files_to_delete:
            os.remove(curfile)

        basis_filename = os.path.join(datadir, 'simple_image.fits')
        basis_header = fits.getheader(basis_filename)
        basis_data = fits.getdata(basis_filename, 0)

        # star is at 155, 122 
        x0 = 155.
        y0 = 122.

        semimajor = [0., 0., 0.]
        period = [0., 0., 0.]
        semimajor[2] = 30.
        period[2] = 50.
        period[1] = period[2] / 2.
        period[0] = period[2] / 3.
        semimajor[1] = (((semimajor[2]**3)/(period[2]**2))*(period[1]**2))**(1./3.)
        semimajor[0] = (((semimajor[2]**3)/(period[2]**2))*(period[0]**2))**(1./3.)

        t = 0.
        filenum = 1

        font = ImageFont.truetype("/Library/Fonts/Courier New Bold.ttf", 14)

        # TODO: figure out how to abstract the following parameter to more generic

        active_mq_info = None
        # comment out next line to deactivate active_mq_info
        active_mq_info = {'server':'oka.lowell.edu', 'port':61613, 'destination_prefix':'fake_fits_maker.ztv.'}
        if active_mq_info is not None:
            try:
                conn = stomp.Connection([(active_mq_info['server'], active_mq_info['port'])])
                conn.start()
                conn.connect()
            except stomp.exception.ConnectFailedException:
                sys.stderr.write('FakeFitsMaker: unable to open connection to ActiveMQ server\n')
                conn = None
            
        while True:
            theta = [0., 0., 0.]
            x = [0., 0., 0.]
            y = [0., 0., 0.]
            new_data = basis_data.copy()
            for i in range(3):
                theta[i] = 2.*np.pi*t/period[i]
                x[i] = x0 + np.sin(theta[i])*semimajor[i]
                y[i] = y0 + np.cos(theta[i])*semimajor[i]
                new_data[np.round(y[i])-1:np.round(y[i])+2,
                         np.round(x[i])-1:np.round(x[i])+2] = 15000.
            base_string = '  t=' + str(t)

            img=Image.new("RGBA", (320, 256), (1,0,0))
            draw = ImageDraw.Draw(img)
            draw.text((10, 256 -16), "current.fits" + base_string, (0,255,0),font=font)
            mask = np.asarray(img.getdata())[:, 0].reshape(256, 320)[::-1, :]
            fits.writeto(os.path.join(datadir, 'current.fits'), new_data*mask, basis_header, clobber=True)

            img=Image.new("RGBA", (320, 256), (1,0,0))
            draw = ImageDraw.Draw(img)
            draw.text((10, 256 -16), 'n' + ('%04i' % filenum) + '.fits' + base_string, (0,255,0),font=font)
            mask = np.asarray(img.getdata())[:, 0].reshape(256, 320)[::-1, :]
            fits.writeto(os.path.join(datadir, 'n' + ('%04i' % filenum) + '.fits'), new_data*mask, basis_header, clobber=True)

            if conn is not None:
                img=Image.new("RGBA", (320, 256), (1,0,0))
                draw = ImageDraw.Draw(img)
                draw.text((10, 256 -16), 'activeMQ: fake_fits_maker.ztv.1' + base_string, (0,255,0),font=font)
                mask = np.asarray(img.getdata())[:, 0].reshape(256, 320)[::-1, :]
                im1 = new_data*mask
                msg = {'image_data':im1}
                hdrs = {}
                hdrs['expires'] = int(60*1000.0 + 1000.0 * time.time())
                conn.send(body=pickle.dumps(msg), destination=active_mq_info['destination_prefix'] + '1', headers=hdrs)
                im2 = im1.max() - im1
                msg = {'image_data':im2}
                conn.send(body=pickle.dumps(msg), destination=active_mq_info['destination_prefix'] + '2', headers=hdrs)
                im3 = im2[:, :]
                im3[:, ::2] = im1[:, ::2]
                msg = {'image_data':im3}
                conn.send(body=pickle.dumps(msg), destination=active_mq_info['destination_prefix'] + '3', headers=hdrs)

            t += 1.
            filenum += 1
            time.sleep(1.0)
            
if __name__ == '__main__':
    # FakeFitsMaker()
    pass
