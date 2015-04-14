from __future__ import absolute_import
import subprocess
import os
import os.path
import pickle
import numpy as np
from .ztv_lib import send_to_stream, StreamListener, StreamListenerTimeOut
import importlib

class Error(Exception):
    pass


# TODO:  add methods to ZTV() for everything conceivable....


class ZTV():
    """
    ZTV Class:
    This is the primary way of opening and interacting with a ztv gui instance.
    Optional keyword arguments:
        title:  string to be displayed as window title at top of ztv gui
    There are intentionally few keyword arguments.  (The only one is 'title', which sets
    the name at the top of the ztv gui window.)

    Other parameters should be set by calling methods, e.g.:
        import numpy as np
        from ztv import ZTV
        z = ZTV(title="My custom ZTV title")
        z.load(np.random.randint(2**16, size=[256, 256]))
        z.set_cmap('jet')
        z.set_minmax(0.3 * (2**16), 0.7 * (2**16))
    """
    def __init__(self, title=None, control_panels_module_path=None):
        # TODO: add generic passthrough of commands, e.g. load fits file? or way to execute sequence of commands from arguments after launch?
        if control_panels_module_path is None:
            cmd = "python -c 'from ztv.ztv import ZTVMain ; ZTVMain(launch_listen_thread=True,"
        else:
#             cmd = ("python -c 'from ztv.ztv import ZTVMain ; control_panels_module = None ; ZTVMain(launch_listen_thread=True, " +
#                    "control_panels_to_load=control_panels_module.control_panels_to_load,")
            cmd = ("python -c 'from ztv.ztv import ZTVMain ; import importlib ; " + 
                   "control_panels_module = importlib.import_module(\"" + 
                   control_panels_module_path + "\") ; ZTVMain(launch_listen_thread=True, " +
                   "control_panels_to_load=control_panels_module.control_panels_to_load,")
        if title is not None:
            cmd += 'title="' + title + '",'
        cmd += 'masterPID=' + str(os.getpid()) +")'"
        self._subproc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        self.stream_listener = StreamListener(self._subproc.stdout)

    def close(self):
        """
        Shutdown this instance of ZTV
        """
        send_to_stream(self._subproc.stdin, "kill_ztv")
        # self._subproc.terminate()   # TODO: neither .terminate() nor .kill() seem to close out the subprocess, something must be holding it up.

    def _load_numpy_array(self, image):
        """
        Load a numpy array into the image.

        Currently only accepts 2-d arrays
        """
        if isinstance(image, np.ndarray):
            send_to_stream(self._subproc.stdin, ('load_numpy_array', image))
        else:
            raise Error('Tried to send type {} instead of a numpy array'.format(type(image)))

    def _validate_fits_filename(self, filename):
        if isinstance(filename, str):
            if filename.lower().endswith('.fits') or filename.lower().endswith('.fits.gz'):
                if os.path.isfile(filename):
                    return True
                else:
                    raise Error("Cannot find file: {}".format(filename))
            else:
                raise Error("Requested filename ({}) does not end with .fits, .fits.gz, " +
                            "or other capitalization of those".format(filename))
        else:
            raise Error("_load_fits_file requires string input, not type: {}".format(type(filename)))
        return False

    def _load_fits_file(self, filename):
        """
        Load a fits file by name.  Can handle *.fits and *.fits.gz
        (or any other capitalization of those file suffixes)
        """
        if self._validate_fits_filename(filename):
            send_to_stream(self._subproc.stdin, ('load_fits_file', filename))

    def load(self, input):
        """
        Load a new image, accepts:
            - numpy array
            - fits filename (e.g. *.fits, *.fits.gz, *.FITS, etc
            TODO: add other input formats, such as fits file
        """
        if isinstance(input, np.ndarray):
            self._load_numpy_array(input)
        elif isinstance(input, str) and self._validate_fits_filename(input):
            self._load_fits_file(input)
        else:
            raise Error("Unrecognized input to ZTV.load(): {}".format(input))

    def load_default_image(self):
        """
        Load the default nonsense image
        """
        send_to_stream(self._subproc.stdin, "load_default_image")

    def get_available_cmaps(self):
        """
        Returns available color maps as a list of strings
        """
        send_to_stream(self._subproc.stdin, "get_available_cmaps")
        try:
            x = self.stream_listener.read_pickled_message(timeout=10.)
        except StreamListenerTimeOut:
            raise Error("get_available_cmaps did not receive return value from ztv.")
        else:
            if x[0] == 'available_cmaps':
                return x[1]
            else:
                raise Error("Unrecognized return value from ztv. {}".format(x))

    def set_cmap(self, cmap):
        """
        Set the colormap.

        A list of available colormaps can be gotten with:   ZTV.get_available_cmaps

        The requested colormap must be in the list of available colormaps, or, it's reverse:
            e.g. 'gray' is in the list, but one can request either 'gray' or 'gray_r'
                 'Blues_r' is in the list, but one can request either 'Blues' or 'Blues_r'
        """
        send_to_stream(self._subproc.stdin, ('set_cmap', cmap))

    def invert_cmap(self):
        """
        Invert the current colormap
        """
        send_to_stream(self._subproc.stdin, 'invert_cmap')

    def reset_minmax(self):
        """
        Reset the min/max to the image's full range
        """
        send_to_stream(self._subproc.stdin, 'set_clim_to_minmax')

    def auto_minmax(self):
        """
        Set the min/max to the automatic setting
        """
        send_to_stream(self._subproc.stdin, 'set_clim_to_auto')

    def set_minmax(self, minval=None, maxval=None):
        """
        Set min/max clipping of values in image display.
        If min > max, then will invert the colormap.
        If minval=None (or maxval=None) then that limit is not changed.

        See ZTV.reset_minmax() for resetting the min/max to the image's full range
        """
        send_to_stream(self._subproc.stdin, ('set_clim', (minval, maxval)))

    def reset_zoom_and_center(self):
        send_to_stream(self._subproc.stdin, 'reset_zoom_and_center')

    def set_zoom(self, zoom):
        send_to_stream(self._subproc.stdin, ('set_zoom_factor', zoom))

    def set_xy_center(self, *args):
        if len(args) == 1:
            x,y = args[0]
        else:
            x,y = args[0], args[1]
        send_to_stream(self._subproc.stdin, ('set_xy_center', (x, y)))

    def add_activemq(self, server=None, port=61613, destination=None):
        if server is None:
            raise Error('Must specify a server address in server keyword, e.g.  "myserver.mywebsite.com"')
        if destination is None:
            raise Error('Must specify a message queue to follow in destination keyword')
        send_to_stream(self._subproc.stdin, ('add_activemq_instance', (server, port, destination)))

