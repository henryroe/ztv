import sys
import pickle
from threading import Thread
from Queue import Queue, Empty


# point is to make improbable that would ever happen to appear inside a pickled image and be mistaken
# Note that because you may be loading image data and random strings will occur... best to have a big
# *10 on this message string.  *1 or *2 might not be enough....
end_of_message_message = ("---EndOfMessage---"*10) + "\n"   

def send_to_stream(stream, msg): 
    """
    Pickle & send to stdout a message.
    Used primarily to communicate back-and-forth with a separately launched ztv process.
    """
    if isinstance(msg, str):
        msg = (msg,)
    pkl = pickle.dumps(msg)
    stream.write(pkl + '\n' + end_of_message_message)
    stream.flush()

class UnexpectedEndOfStream(Exception): pass

class StreamListenerTimeOut(Exception): pass

def _accumulate_to_queue(stream, queue):
    while True:
        line = stream.readline()
        if line:
            queue.put(line)
        else:
# TODO: rather than return, should really raise the Error, but then code elsewhere needs to be catching for it
#             raise UnexpectedEndOfStream
            return

class StreamListener():
    def __init__(self, stream):
        """
        stream: e.g, stdin/stdout
        """
        self.stream = stream
        self.queue = Queue()
        self.thread = Thread(target=_accumulate_to_queue, args=(self.stream,self.queue))
        self.thread.daemon = True
        self.thread.start() 

    def read_pickled_message(self, timeout=None):
        try:
            block = timeout is not None
            msg = ""
            while not msg.endswith('\n' + end_of_message_message):
                msg += self.queue.get(block=block, timeout=timeout)
            return pickle.loads(msg.replace('\n' + end_of_message_message, ''))
        except Empty:
            raise StreamListenerTimeOut


def listen_to_pipe(pipe, timeout=None):
    """
    Will listen on pipe until has seen end_of_message_message, then strip the 
    end_of_message_message and return the unpickled version of the preceding message
    
    If timeout is None, then will just do a traditional blocking call of readline() 
                        (i.e. will *never* return if a newline never comes in)
    If timeout is not None, then if length of output hasn't changed in timeout seconds,
                        then raise a timeout exception
    """
    in_str = ""
    if timeout is None:
        while not in_str.endswith('\n' + end_of_message_message):
            in_str += pipe.readline()
    else:
        pass
    return pickle.loads(in_str.replace('\n' + end_of_message_message, ''))