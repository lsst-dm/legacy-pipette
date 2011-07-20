#!/usr/bin/env python

import sys
import time
import atexit

"""Timing decorator, for measuring execution time.

This is the "timecall" part of "profilehooks" from
http://mg.pov.lt/profilehooks/svn/trunk/profilehooks.py,
with some extensions to enable run-time configuration.

The license for the original code, profilehooks, is:

  Copyright (c) 2004--2008 Marius Gedminas <marius@pov.lt>
  Copyright (c) 2007 Hanno Schlichting
  Copyright (c) 2008 Florian Schulze

  Released under the MIT licence since December 2006:

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
"""



def timecall(fn=None, active=False, immediate=False, report=True):
    """Wrap `fn` and print its execution time.

    Example::

        @timecall(active=True)
        def somefunc(x, y):
            time.sleep(x * y)

        somefunc(2, 3)

    will report the total time taken in that call at program termination.
    Immediate reports (for each function call) can be obtained with
    immedate=True.  The final report can be disabled with report=False.
    
    By default (no options passed to decorator @timecall), timing is OFF,
    but can be turned on using TimerConfig:

        TimerConfig.setActive(True)

    Additional run-time configuration is available using the TimerConfig singleton
    class (immediate reports for all decorated functions, different timer).
    """
    if fn is None: # @timecall() syntax -- we are a decorator maker
        def decorator(fn):
            return timecall(fn, immediate=immediate, report=report)
        return decorator
    # @timecall syntax -- we are a decorator.
    fp = FuncTimer(fn, immediate=immediate, report=report)
    # We cannot return fp or fp.__call__ directly as that would break method
    # definitions, instead we need to return a plain function.
    def new_fn(*args, **kw):
        return fp(*args, **kw)
    new_fn.__doc__ = fn.__doc__
    new_fn.__name__ = fn.__name__
    new_fn.__dict__ = fn.__dict__
    new_fn.__module__ = fn.__module__
    return new_fn



class TimerConfig(object):
    """Singleton class providing global run-time configuration of function timing."""

    # Singletonisation
    # From http://stackoverflow.com/questions/42558/python-and-the-singleton-pattern/1810367#1810367
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TimerConfig, cls).__new__(cls, *args, **kwargs)
            cls._instance.active = False
            cls._instance.immediate = False
            cls._instance.timer = time.time
        return cls._instance

    @classmethod
    def setActive(cls, active):
        self = cls()
        active, self.active = self.active, active
        return active

    @classmethod
    def getActive(cls):
        return cls().active

    @classmethod
    def setImmediate(cls, immediate):
        self = cls()
        immediate, self.immediate = self.immediate, immediate
        return immediate

    @classmethod
    def getImmediate(cls):
        return cls().immediate

    @classmethod
    def setTimer(cls, timer):
        self = cls()
        timer, self.timer = self.timer, timer
        return timer

    @classmethod
    def getTimer(cls):
        return cls().timer


class FuncTimer(object):
    def __init__(self, fn, immediate, report):
        self.fn = fn
        self.ncalls = 0
        self.totaltime = 0
        self.immediate = immediate
        if report:
            atexit.register(self.atexit)

    def __call__(self, *args, **kw):
        """Profile a singe call to the function."""
        fn = self.fn
        config = TimerConfig()
        if not config.getActive():
            return fn(*args, **kw)

        timer = config.getTimer()
        self.ncalls += 1
        try:
            start = timer()
            return fn(*args, **kw)
        finally:
            duration = timer() - start
            self.totaltime += duration
            if self.immediate or config.getImmediate():
                funcname = fn.__name__
                filename = fn.func_code.co_filename
                lineno = fn.func_code.co_firstlineno
                print >> sys.stderr, "\n  %s (%s:%s):\n    %f seconds\n" % (
                                        funcname, filename, lineno, duration)

    def atexit(self):
        if not self.ncalls:
            return
        funcname = self.fn.__name__
        filename = self.fn.func_code.co_filename
        lineno = self.fn.func_code.co_firstlineno
        print ("TIMER on %s (%s:%s): %d calls, %f seconds%s" % (
            funcname, filename, lineno, self.ncalls, self.totaltime,
            " (%f seconds per call)" % (self.totaltime / self.ncalls) if self.ncalls > 1 else ""))

