################################################################################
# Python class for reading FEI Velox 4D STEM .mrc files into sidpy Dataset
# and extracting all metadata
#
# Written by Austin Houston, UTK 2024
#
# based on MRC2014 file format:
# https://www.ccpem.ac.uk/mrc_format/mrc2014.php
#
# and corresponding mrcfile package:
# https://pypi.org/project/mrcfile/
################################################################################


import json
import h5py
import sys
import numpy as np
import dask.array as da
from numba import njit
import sidpy
import mrcfile
try:
    from tqdm.auto import tqdm
    tqdm_available = True
except ImportError:
    tqdm_available = False

__all__ = ["MRCReader", "version"]

version = '1.0'


class MRCReader(sidpy.Reader):

    def __init__(self, file_path):
        super(MRCReader, self).__init__(file_path)
        self.file_path = file_path
        self.metadata = None
        self.data = None
        self.scan_shape = None

        self.dataset = None

            
    def read(self, handedness='right', scan_pixel_size=None):
        # scan pixel size needs to be in meters, if you know it
        # handedness is either 'right' or 'left', and determines the handedness of the scan
        # not all .mrc files have the handedness embedded, so if your file looks wrong, try changing this

        # read with 
        mrc =  mrcfile.mmap(self.file_path, permissive=True)

        # data
        mrc_data = mrc.data

        # metadata
        extended_header = mrc.indexed_extended_header
        metadata_labels = extended_header.dtype.names
        metadata_labels = [label for label in metadata_labels]

        # Reshape the data
        scan_shape_params = ['Scan size right', 'Scan size left', 'Scan size top', 'Scan size bottom']

        sizes = []
        for label in scan_shape_params:
            size = np.unique(extended_header[label])
            sizes.append(size)
        sizes = np.array(sizes).flatten()
        y_shape = int(np.abs(sizes[0] - sizes[1]))
        x_shape = int(np.abs(sizes[2] - sizes[3]))

        if handedness=='right':
            reshape_target = (x_shape, y_shape, mrc_data.shape[-2], mrc_data.shape[-1])
        elif handedness=='left':
            reshape_target = (y_shape, x_shape, mrc_data.shape[-2], mrc_data.shape[-1])
        else:
            print('Handedness must = "right" or "left"')

        try:
            self.data = np.reshape(mrc_data, reshape_target)
        except ValueError:
            print(f'Error reshaping data: {mrc_data.shape} to {reshape_target}')
            print(f'the scan must have been stopped early, on the microscope - this creates issues still')
            print(f'sorry, we do not support reading point cloud versions of this data yet')


        # These 'pixel sizes' are usually in the order of 10^8: This the camera pixel size, not the scan step size.
        # I've talked to thermofisher and plan to update this eventually (2024-9-6)
        camera_pixel_sizes = []
        for label in ['Pixel size X', 'Pixel size Y']:
            size = np.unique(extended_header[label])
            size *= 1e-10 # conversion from 1/m to 1/Angstrom
            camera_pixel_sizes.append(size)

        # scan pixel size
        if scan_pixel_size:
            # if scan pixel size is given, use it
            self.scan_pixel_size = scan_pixel_size * 1e10 # conversion from m to Angstrom
            self.scan_size_units = 'Å'
        else:
            self.scan_pixel_size = 1
            self.scan_size_units = 'pixels'


        # make metadata dictionary
        metadata = {}
        for label in metadata_labels:
            # later, we may want to remove 'np.unique()', but I see no problems now
            metadata[label] = np.unique(extended_header[label])
        self.metadata = metadata


        # create sidpy Dataset
        dataset = sidpy.Dataset.from_array(self.data, name='MRC_000', chunks=(1, 1, reshape_target[-2], reshape_target[-1]))
        # add metadata dictionary
        dataset.original_metadata = self.metadata
        dataset.data_type = 'image_4d'

        dataset.set_dimension(0, sidpy.Dimension(np.arange(dataset.shape[0]) * self.scan_pixel_size, 
                                                name='x', units=self.scan_size_units, quantity='length',
                                                dimension_type='spatial'))

        dataset.set_dimension(1, sidpy.Dimension(np.arange(dataset.shape[1]) * self.scan_pixel_size,
                                                name='y', units=self.scan_size_units, quantity='length',
                                                dimension_type='spatial'))

        dataset.set_dimension(2, sidpy.Dimension(np.arange(dataset.shape[2]) * camera_pixel_sizes[0],
                                                name='u', units='1/Å', quantity='angle',
                                                dimension_type='reciprocal'))

        dataset.set_dimension(3, sidpy.Dimension(np.arange(dataset.shape[3]) * camera_pixel_sizes[1],
                                                name='v', units='1/Å', quantity='angle',
                                                dimension_type='reciprocal'))

        return {'Channel_000': dataset}
    
