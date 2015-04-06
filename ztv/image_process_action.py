import sys

class ImageProcessAction():
    def __init__(self, math_function, x2):
        """
        math_function - must accept two arrays (x1, x2) and return the resulting array
                        e.g. numpy.add, numpy.subtract, numpy.divide
                        x1 will be the "current" display image
        x2 is provided at the creation of the instance of the class
        e.g.
        import numpy as np
        proc_fxn = ImageProcessAction(np.subtract, np.ones([5,5]))
        im = np.random.poisson(10, [5,5])
        print(im)
        print(proc_fxn(im))
        """
        self.math_function = math_function
        self.x2 = x2
    def __call__(self, x1):
        if x1.shape != self.x2.shape:
            sys.stderr.write("Warning: image process action not performed because shapes of arrays do not match")
            return x1
        return self.math_function(x1, self.x2)

