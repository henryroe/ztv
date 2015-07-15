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
        
        NOTE: we are taking advantage of the nice feature of numpy that makes dealing with 2-d processes
        on 3-d image stacks much easier:
            im_stack = np.random.normal(size=[10, 256, 256])
            dark = np.random.normal(size=[256, 256])
        the one line:
            im_stack_processed = im_stack - dark
        is equivalent to:
            im_stack_processed = im_stack.copy()
            for i in np.arange(10):
                im_stack_processed[i,:,:] = im_stack[i,:,:] - dark
        """
        self.math_function = math_function
        self.x2 = x2
    def __call__(self, x1):
        if (x1.shape[-1] != self.x2.shape[-1]) or (x1.shape[-2] != self.x2.shape[-2]):
            sys.stderr.write("Warning: image process action not performed because x/y shapes of arrays do not match\n")
            return x1
        return self.math_function(x1, self.x2)

