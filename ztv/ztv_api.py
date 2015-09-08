from __future__ import absolute_import
import subprocess
import os
import pickle
import numpy as np
from .ztv_lib import send_to_stream, StreamListener, StreamListenerTimeOut
import importlib
from codecs import open  # To use a consistent encoding

class Error(Exception):
    pass

base_dir = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(base_dir, "__about__.py")) as f:
    exec(f.read(), about)


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
        z.cmap('jet')
        z.minmax(0.3 * (2**16), 0.7 * (2**16))
    """
    def __init__(self, title=None, control_panels_module_path=None, default_data_dir=None,
                 default_autoload_pattern=None):
        self.__version__ = about["__version__"]
        # Note: prefer pythonw vs. python for launching in on OS X because in some cases
        # python will not connect correctly with Frameworks necessary for wxPython, while
        # pythonw will.  But, pythonw not available on all systems.
        find_python_str = "`echo \`which pythonw\` \`which python\` | awk '{print $1}'`"
        if control_panels_module_path is None:
            cmd = find_python_str + " -c 'from ztv.ztv import ZTVMain ; ZTVMain(launch_listen_thread=True,"
        else:
            cmd = (find_python_str + "python -c 'from ztv.ztv import ZTVMain ; import importlib ; " + 
                   "control_panels_module = importlib.import_module(\"" + 
                   control_panels_module_path + "\") ; ZTVMain(launch_listen_thread=True, " +
                   "control_panels_to_load=control_panels_module.control_panels_to_load,")
        if title is not None:
            cmd += 'title="' + title + '",'
        if default_data_dir is not None:
            cmd += 'default_data_dir="' + default_data_dir + '",'
        if default_autoload_pattern is not None:
            cmd += 'default_autoload_pattern="' + default_autoload_pattern + '",'
        cmd += 'masterPID=' + str(os.getpid()) +")'"
        self._subproc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        self.stream_listener = StreamListener(self._subproc.stdout)
        self.clim = self.minmax   # make an alias

    def close(self):
        """
        Shutdown this instance of ZTV
        """
        self._send_to_ztv("kill_ztv")

    def _request_return_value_from_ztv(self, request_message, expected_return_message_title=None, timeout=10.):
        """
        routine to request info from ztv by sending message and receiving response
        """
        if expected_return_message_title is None and request_message.startswith('get_'):
            expected_return_message_title = request_message[4:]
        elif expected_return_message_title is None:
            expected_return_message_title = request_message
        self._send_to_ztv(request_message)
        try:
            x = self.stream_listener.read_pickled_message(timeout=timeout)
        except StreamListenerTimeOut:
            raise Error("did not receive return value from ztv in response to request: {}".format(request_message))
        else:
            if x[0] == expected_return_message_title:
                return x[1]
            else:
                raise Error("Unrecognized return value from ztv ({}) " +
                            "in response to request: {}".format(x, request_message))

    def _send_to_ztv(self, msg):
        send_to_stream(self._subproc.stdin, msg)

    def _load_numpy_array(self, image):
        """
        Load a numpy array into the image.
        """
        if isinstance(image, np.ndarray):
            self._send_to_ztv(('load_numpy_array', image))
        else:
            raise Error('Tried to send type {} instead of a numpy array'.format(type(image)))

    def _validate_fits_filename(self, filename):
        """
        check that input filename ends with .fits or .fits.gz (any combo of upper/lower case)
        """
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
            self._send_to_ztv(('load_fits_file', filename))

    def load(self, input):
        """
        Load a new image, accepts:
            - numpy array
            - fits filename (e.g. *.fits, *.fits.gz, *.FITS, etc
            TODO: add other input formats, such as hdulist of already read-in fits file
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
        self._send_to_ztv("load_default_image")

    def cmap(self, cmap=None):
        """
        Set the colormap.

        A list of available colormaps can be gotten with:   ZTV.cmaps_list

        The requested colormap must be in the list of available colormaps, or, it's reverse:
            e.g. 'gray' is in the list, but one can request either 'gray' or 'gray_r'
                 'Blues_r' is in the list, but one can request either 'Blues' or 'Blues_r'
                 matching the input to the available cmaps is done independent of lower/upper case
                 cmap_inverted will be set as necessary to comply with the request.
                 This means that the returned cmap name may not match the input.
                 
        returns the current (new) colormap
        """
        if isinstance(cmap, str):
            self._send_to_ztv(('set_cmap', cmap))
        return self._request_return_value_from_ztv('get_cmap')
        
    def cmaps_list(self):
        """
        returns the available color maps as a list of strings
        """
        return self._request_return_value_from_ztv('get_available_cmaps')

    def invert_cmap(self, state=None):
        """
        state:  True -> set invert=True
                False -> set invert=False
                None -> do nothing
        Returns the current inversion state
        """
        if state is not None:
            self._send_to_ztv(('set_cmap_inverted', state))
        return self._request_return_value_from_ztv('get_is_cmap_inverted')

    def scaling(self, scaling=None):
        """
        Set the scaling.  (e.g. 'linear', 'log')

        A list of available scalings can be gotten with:   ZTV.scalings_list

        The requested scaling must be in the list of available scalings.
        (independent of case, e.g. 'linear' or 'Linear' are both valid
        
        returns the current (new) scaling
        """
        if isinstance(scaling, str):
            self._send_to_ztv(('set_scaling', scaling))
        return self._request_return_value_from_ztv('get_scaling')

    def scalings_list(self):
        """
        returns the available scalings as a list of strings
        """
        return self._request_return_value_from_ztv('get_available_scalings')

    def set_minmax_to_full_range(self):
        """
        Reset the min/max to the image's full range
        
        returns current (new) min/max range
        """
        self._send_to_ztv('set_clim_to_minmax')
        return self._request_return_value_from_ztv('get_clim')

    def set_minmax_to_auto(self):
        """
        Set the min/max to the automatic setting
        
        returns current (new) min/max range
        """
        self._send_to_ztv('set_clim_to_auto')
        return self._request_return_value_from_ztv('get_clim')

    def minmax(self, minval=None, maxval=None):
        """
        Set min/max clipping of values in image display.
        If min > max, then will invert the colormap.
        If minval=None (or maxval=None) then that limit is not changed.

        See ZTV.set_minmax_to_full_range() for resetting the min/max to the image's full range
        
        returns current (new) min/max range
        """
        if minval is not None and maxval is not None:
            self._send_to_ztv(('set_clim', (minval, maxval)))
        return self._request_return_value_from_ztv('get_clim')

    def reset_zoom_and_center(self):
        """
        Reset pan to center of image
        Reset zoom to image just fitting in primary display frame
        """
        self._send_to_ztv('reset_zoom_and_center')
  
    def zoom(self, zoom=None):
        """
        Set zoom factor
        
        returns current zoom factor
        """
        if zoom is not None:
            self._send_to_ztv(('set_zoom_factor', zoom))
        return self._request_return_value_from_ztv('get_zoom_factor')

    def xy_center(self, *args):
        """
        pan the image to place x,y at the center of the primary image frame
        
        returns the current (new) x/y center of the primary image frame
        """
        if len(args) > 0:
            if len(args) == 1:
                x,y = args[0]
            else:
                x,y = args[0], args[1]
            self._send_to_ztv(('set_xy_center', (x, y)))
        return self._request_return_value_from_ztv('get_xy_center')

    def add_activemq(self, server=None, port=61613, destination=None):
        """
        TODO: write docstring
        """
        if server is None:
            raise Error('Must specify a server address in server keyword, e.g.  "myserver.mywebsite.com"')
        if destination is None:
            raise Error('Must specify a message queue to follow in destination keyword')
        self._send_to_ztv(('add_activemq_instance', (server, port, destination)))

    def frame_number(self, n=None, relative=False):
        """
        If 3-d image is loaded set the frame number to be displayed.
        Default (relative=False) is to set to frame number n (automatically clipped to 0->size of 3-d stack)
        Negative n will count back from end of image stack, e.g. -1 is last, -2 is second to last.
        Optionally (relative=True) will add n to current frame number (-1 go back one, 1 advance one)
        
        returns current (new) frame number
        """
        if n is not None:
            if relative:
                flag = 'relative'
            else:
                flag = 'absolute'
            self._send_to_ztv(('set_cur_display_frame_num', (n, flag)))
        return self._request_return_value_from_ztv('get_cur_display_frame_num')
        
    def sky_frame(self, filename=None):
        """
        Set sky frame to filename and turn on sky subtraction
        To turn on sky subtraction with already loaded filename pattern, set filename=True
        To turn off sky subtraction, set filename=False
        (filename=None will do nothing, just return current status)
        
        returns tuple of current sky subtraction status (True/False) and current sky frame filename
        """
        if filename is True or filename is False:
            self._send_to_ztv(('set_sky_subtraction_status', filename))
        elif filename is not None:
            self._send_to_ztv(('set_sky_subtraction_filename', filename))
        return self._request_return_value_from_ztv('get_sky_subtraction_status_and_filename')
        
    def flat_frame(self, filename=None):
        """
        Set flat frame to filename and turn on flat field division
        To turn on flat field division with already loaded filename pattern, set filename=True
        To turn off flat field division, set filename=False
        (filename=None will do nothing, just return current status)
        
        returns current flat frame filename
        """
        if filename is True or filename is False:
            self._send_to_ztv(('set_flat_division_status', filename))
        elif filename is not None:
            self._send_to_ztv(('set_flat_division_filename', filename))
        return self._request_return_value_from_ztv('get_flat_division_status_and_filename')
        
    def autoload_filename_pattern(self, filename=None):
        """
        Set filename pattern for autoload to filename and turn on auto-load
        To turn on auto-loading with already loaded filename pattern, set filename=True
        To turn off auto-loading, set filename=False
        (filename=None will do nothing, just return current status)

        returns current auto-load filename pattern
        """
        if filename is True or filename is False:
            self._send_to_ztv(('set_autoload_filename_pattern_status', filename))
        elif filename is not None:
            self._send_to_ztv(('set_autoload_filename_pattern', filename))
        return self._request_return_value_from_ztv('get_autoload_status_and_filename_pattern')

    def autoload_pause_seconds(self, seconds=None):
        """
        Set pause time in seconds (will adjust to nearest available value)
        returns current autoload pause time
        """
        if seconds is not None:
            self._send_to_ztv(('set_autoload_pausetime', seconds))
        return self._request_return_value_from_ztv('get_autoload_pausetime')

    def slice_plot(self, pts=None, show_overplot=True):
        """
        pts: of form [[x0, y0], [x1, y1]]
        show_overplot:  If True, then show the over-plotted line
                        If False, then hide the line, although plot panel itself will continue to update
        Returns current (new) pts
        """
        if pts is not None:
            self._send_to_ztv(('set_new_slice_plot_xy0', pts[0]))
            self._request_return_value_from_ztv('get_slice_plot_coords')  # dummy call to give time to update so that return is correct.
            self._send_to_ztv(('set_new_slice_plot_xy1', pts[1]))
        if show_overplot:
            self._send_to_ztv('show_plot_panel_overplot')
        else:
            self._send_to_ztv('hide_plot_panel_overplot')
        return self._request_return_value_from_ztv('get_slice_plot_coords')
        
    def stats_box(self, xrange=None, yrange=None, show_overplot=None):
        """
        box: of form [[x0, y0], [x1, y1]]
        show_overplot:  If True, then show the over-plotted box
                        If False, then hide the box, although stats panel itself will continue to update
                        If None, leave unchanged
        Returns current (new) box
        """
        self._send_to_ztv(('set_stats_box_parameters', {'xrange':xrange, 'yrange':yrange,
                                                                          'show_overplot':show_overplot}))
        waiting = self._request_return_value_from_ztv('set_stats_box_parameters_done')
        return self._request_return_value_from_ztv('get_stats_box_info')

    def aperture_phot(self, xclick=None, yclick=None, radius=None, inner_sky_radius=None, outer_sky_radius=None,
                      show_overplot=None):
        """
        Send updated parameters to the Aperture Photometry control panel.
        Any unmodified arguments will be left unmodified in ztv. 
        (e.g. can change just x/y without respecifying radius, or change radius without respecifying x/y)
        x,y:  coordinates, will be used as starting point to centroid on (as if user had clicked at that x/y)
        radius:  Object radius
        inner_sky_radius,outer_sky_radius:  defines the sky annulus
        show_overplot:  If True, then show the over-plotted apertures on the display
                        If False, then hide the apertures, although phot panel itself will continue to update
                        If None, don't change.
        returns a dict with output photometry
        """  
        self._send_to_ztv(('set_aperture_phot_parameters', 
                                             {'xclick':xclick, 'yclick':yclick, 'radius':radius, 
                                              'inner_sky_radius':inner_sky_radius, 'outer_sky_radius':outer_sky_radius,
                                              'show_overplot':show_overplot}))
        waiting = self._request_return_value_from_ztv('set_aperture_phot_parameters_done')
        return self._request_return_value_from_ztv('get_aperture_phot_info')

    def control_panel(self, name):
        """
        Switch to the control panel `name`.  `name` is matched against the names shown in the gui tabs, except case insenstive. 
        """
        self._send_to_ztv(('switch_to_control_panel', name))
        