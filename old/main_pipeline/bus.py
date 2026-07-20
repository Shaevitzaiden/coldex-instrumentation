# -------------
# The bus!
#
# Not much going on here, just a small class with two methods. This can read and write a message (with
# locking, so we don't get errors if two calls try to read/write at the same time) so is really handy
# for passing information around between classes and methods.
# -------------

from readerwriterlock import rwlock

class Bus():
    """Class that sets up a bus to pass information around with read/write locking"""
    def __init__(self):
        self.message = None
        self.lock = rwlock.RWLockWriteD() # sets up a lock to prevent simultanous reading and writing

    def write(self, message):
        with self.lock.gen_wlock():
            self.message = message

    def read(self):
        with self.lock.gen_rlock():
            message = self.message
        return message