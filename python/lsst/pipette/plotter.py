#!/usr/bin/env python

import matplotlib
matplotlib.use('pdf')
import matplotlib.backends.backend_pdf
import matplotlib.pyplot as plot
import numpy


def gaussian(param, x):
    norm = param[0]
    offset = param[1]
    width = param[2]
    return norm * numpy.exp(-((x - offset)/width)**2)    

class Plotter(object):
    def __init__(self, name):
        self.name = name
        if not self.name.endswith(".pdf"):
            self.name += ".pdf"
        self.pdf = matplotlib.backends.backend_pdf.PdfPages(self.name)

    def close(self):
        self.pdf.close()

    def xy(self, x, y, axis=None, title=None):
        plot.figure()
        plot.scatter(x, y, marker='x')
        if axis is not None:
            plot.axis(axis)
        if title is not None:
            plot.title(title)
        self.pdf.savefig()
        plot.close()

    def histogram(self, data, range, bins=51, mean=None, sigma=None, title=None):
        plot.figure()
        n, bins, patches = plot.hist(data, bins=bins, range=range, normed=False,
                                     histtype='bar', align='mid')
        norm = n.max()
        if mean is not None and sigma is not None:
            gauss = gaussian([norm, mean, sigma], bins)
            plot.plot(bins, gauss, 'r-')
        if title is not None:
            plot.title(title)
        self.pdf.savefig()
        plot.close()

    def xy2(self, x1, y1, x2, y2, axis1=None, axis2=None, title1=None, title2=None):
        plot.figure()
        plot.subplot(2, 1, 1)
        if axis1 is not None:
            plot.axis(axis1)
        plot.scatter(x1, x2, marker='+')
        if title1 is not None:
            plot.title(title1)

        plot.subplot(2, 1, 2)
        if axis2 is not None:
            plot.axis(axis2)
        plot.scatter(x2, y2, marker='+')
        if title2 is not None:
            plot.title(title2)

        self.pdf.savefig()
        plot.close()

    def quivers(self, x, y, dx, dy, title=None):
        plot.figure()
        plot.quiver(x, y, dx, dy)
        if title is not None:
            plot.title(title)
        self.pdf.savefig()
        plot.close()
