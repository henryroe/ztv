
# can run this with:
# start-anaconda
# source activate ztv-testing-local
# cd /Users/hroe/Dropbox/py/ztv/trace-testing
# pythonw ztv_trace.py


# this is cribbed/modified from [here](http://stackoverflow.com/questions/8315389/how-do-i-print-functions-as-they-are-called)

import sys
import linecache
import random
import datetime as dt


def tracefunc(frame, event, arg, indent=[0], start_times={}):
    if event != "call" and event != "return":
        return None
    prefix = frame.f_code.co_filename.replace('.pyo','').replace('.pyc','').replace('.py','')
    if '/ztv/' in prefix:
        try:
            class_name = '.' + frame.f_locals['self'].__class__.__name__
        except KeyError:
            class_name = ''
        full_name = prefix + class_name + '.' + frame.f_code.co_name 
        full_name = full_name[full_name.find('py/ztv/') + 7:].replace('/', '.')
        if event == "call":            
            indent[0] += 2
            now = dt.datetime.utcnow()
            start_times[indent[0]] = now
            print now.strftime('%H:%M%:%S.%f'), "-" * indent[0] + "> call function", full_name
        elif event == "return":
            now = dt.datetime.utcnow()
            print '{0:10.6f}     '.format((now - start_times.pop(indent[0])).total_seconds()), "<" + "-" * indent[0], "exit function", full_name
            indent[0] -= 2
        return tracefunc



def main():
    from ztv.ztv import ZTVMain
    z = ZTVMain(default_autoload_pattern='/Users/hroe/Dropbox/py/ztv/trace-testing/*fits*')
    
    
sys.settrace(tracefunc)
main()
