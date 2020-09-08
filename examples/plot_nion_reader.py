"""
======================================
Reader for proprietary Nion file format
======================================

**Gerd Duscher**

9/08/2020

This document illustrates an example of extracting data out of dm3
(Digirtal Micrograph) file.


Introduction
------------
The Nion Swift software stores the data in two different data formats with the extenson ``.ndata`` and ``.h5``.
Both can be read with the nion_reader of the ScopeReaders package
We read and plot such files here.

Import all necessary packages
=============================
There are a few setup procedures that need to be followed before any code is written. In this step, we simply load a
few python packages that will be necessary in the later steps.
"""
import numpy as np
import matplotlib.pyplot as plt
#import file_tools_nsid as ft


import sys
sys.path.append('../../sidpy')
from sidpy.io.interface_utils import openfile_dialog, get_QT_app
sys.path.append('../../pyNSID')
import pyNSID
sys.path.append('../')
from ScopeReaders.em.tem.nion_reader import NionReader

####################################################################################
# Open a file dialog
# ===================
# Here we select the name of the file to open. We will be using the sidpy interface to do that.
# We start QT as a backend for the dialog first (in a notebook the magic command ``%gui qt5``)

app = get_QT_app()

# Then we can open QT file dialog to select a file

file_name = openfile_dialog()
print(file_name)

# catch a bad selection or cancelling of file selection
if len(file_name)<3:
    print('File selection canceled')
    exit()


####################################################################################

####################################################################################
# Read file
# =========
# We use the ScopeReader to read the file into a sidpy dataset.
# All metadata (absolutely everything) is saved in the ``original_metadata`` attribute
# of the sidpy Dataset. If the selected file is not a Nion File you get an ``IOError``.
# either you selected a file not with the right extension (``.h5`` or ``.ndata``) or the
# file is not consistent with the Swift file format.
nion_reader = NionReader(file_name)
dataset = nion_reader.read()
print(dataset)

####################################################################################

###################################################################################
# Plot file
# ==========
# Only one command is necessary to plot the file.

dataset.plot()

####################################################################################

