#!/usr/bin/env python

from lsst.pipette.stages.detrend import Detrend

class Fringe(Detrend):
    def run(self, exposure=None, detrends=None, **kwargs):
        """Fringe subtraction

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        fringe = detrends['fringe']
        raise NotimplementedError, "Fringe subtraction is not yet implemented."

