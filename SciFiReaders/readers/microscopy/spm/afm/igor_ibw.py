# -*- coding: utf-8 -*-
"""
Created on Wed Dec 07 16:04:34 2016

Updated on Fri Sep 11 15:22:00 2020 for ScopeReader

@author: Suhas Somnath, Chris R. Smith, Raj Giridhargopal, Rama Vasudevan
"""

import sys
import numpy as np  # For array operations
import sidpy as sid
from sidpy.sid import Reader
import re
from warnings import warn

try:
    from igor import binarywave as bw
except ModuleNotFoundError:
    print("You don't have igor installed. \
    If you wish to open igor files, you will need to install it \
    (pip install igor) before attempting.")
    bw = None

class IgorMatrixReader(Reader):
    """
    Extracts data and metadata from Igor Binary Wave (.ibw) files exported from MatrixFiles
    This is a very specific reader that cannot be reconciled with the generic ibw reader due to severe inconsistencies.
    Unless you exported Matrix files as ibw files using IGOR5 Exporter v120401, this reader will not work.
    """
    def __init__(self, file_path, *args, **kwargs):
        if bw == None:
            raise ModuleNotFoundError('You attempted to load an Igor file, but this requires igor.\n \
            Please Load it with pip install igor , restart and retry')

        super().__init__(file_path, *args, **kwargs)

    def read(self, verbose=False, parm_encoding='utf-8'):
        """
        Reads the file given in file_path into a sidpy dataset

        Parameters
        ----------
        verbose : Boolean (Optional)
            Whether or not to show  print statements for debugging
        parm_encoding : str, optional
            Codec to be used to decode the bytestrings into Python strings if
            needed. Default 'utf-8'

        Returns
        -------
        sidpy.Dataset : List of sidpy.Dataset objects.
            Multi-channel inputs are separated into individual dataset objects
        """
        file_path = self._input_file_path

        # Load the ibw file first
        ibw_obj = bw.load(file_path)
        ibw_wave = ibw_obj.get('wave')
        parm_dict = self._read_parms(ibw_wave, parm_encoding)
        self.parm_dict =  parm_dict

        data_mat = ibw_obj['wave']['wData']
        if self.parm_dict['datatype']=='image':
            data_mat = np.rot90(data_mat,3)
            xvec = np.linspace(0, self.parm_dict['image_width'], data_mat.shape[1])
            yvec = np.linspace(0, self.parm_dict['image_height'], data_mat.shape[0] )
            
            #make the sidpy dataset
            data_set = sid.Dataset.from_array(data_mat, name= parm_dict['channel_name'])
            data_set.data_type = 'Image'

            #Add quantity and units
            data_set.units = self.parm_dict['channel_unit']
            data_set.quantity =  self.parm_dict['parm_list'][0]

            #Add dimension info
            data_set.set_dimension(0, sid.Dimension(yvec,
                                                    name = 'x',
                                                    units=self.parm_dict['image_units'], quantity = 'x',
                                                    dimension_type='spatial'))
            data_set.set_dimension(1, sid.Dimension(xvec,
                                                    name = 'y',
                                                    units=self.parm_dict['image_units'], quantity='y',
                                                    dimension_type='spatial'))

            # append metadata
            data_set.original_metadata = self.parm_dict
        elif self.parm_dict['datatype']=='Volume CITS':
            #build spectroscopy wave
            bias_start = float(self.parm_dict['parm_list'][self.parm_dict['spec_curve_idx']].split('start =')[1].split(',')[0])
            bias_end = float(self.parm_dict['parm_list'][self.parm_dict['spec_curve_idx']].split('end =')[1].split(',')[0])
            bias_wave = np.linspace(bias_start, bias_end, self.parm_dict['spec_points_per_curve'])
            xvec = np.linspace(0, self.parm_dict['image_width'], data_mat.shape[0])
            yvec = np.linspace(0, self.parm_dict['image_height'], data_mat.shape[1])
            
            #make it sidpy
            data_set = sid.Dataset.from_array(data_mat, name= parm_dict['channel_name'])
            data_set.data_type = sid.DataType.SPECTRAL_IMAGE

            #Add quantity and units
            data_set.units = parm_dict['channel_unit']
            data_set.quantity =  parm_dict['parm_list'][0]
            
            #Add dimension info
            data_set.set_dimension(0, sid.Dimension(xvec,
                                                    name = 'x',
                                                    units=parm_dict['image_units'], quantity = 'x',
                                                    dimension_type='spatial'))
            data_set.set_dimension(1, sid.Dimension(yvec,
                                                    name = 'y',
                                                    units=parm_dict['image_units'], quantity='y',
                                                    dimension_type='spatial'))
            
            data_set.set_dimension(2, sid.Dimension(bias_wave,
                                                    name = 'Bias',
                                                    units='V', quantity='V',
                                                    dimension_type='spectral'))

            # append metadata
            data_set.original_metadata = parm_dict

        # Return the dataset
        return data_set

    @staticmethod
    def _read_parms(ibw_wave, codec='utf-8'):
        """
        Parses the parameters in the provided dictionary

        Parameters
        ----------
        ibw_wave : dictionary
            Wave entry in the dictionary obtained from loading the ibw file
        codec : str, optional
            Codec to be used to decode the bytestrings into Python strings if needed.
            Default 'utf-8'

        Returns
        -------
        parm_dict : dictionary
            Dictionary containing parameters
        """
        parm_string = ibw_wave.get('note')
        if type(parm_string) == bytes:
            try:
                parm_string = parm_string.decode(codec)
            except:
                parm_string = parm_string.decode('ISO-8859-1')  # for older AR software
        parm_string = parm_string.rstrip('\r')
        parm_list = parm_string.split('\r')
        parm_dict = dict()
        for pair_string in parm_list:
            for split_parm in [':', '=']:
                temp = pair_string.split(split_parm)
                if len(temp) == 2:
                    temp = [item.strip() for item in temp]
                    try:
                        num = float(temp[1])
                        parm_dict[temp[0]] = num
                        try:
                            if num == int(num):
                                parm_dict[temp[0]] = int(num)
                        except OverflowError:
                            pass
                    except ValueError:
                        parm_dict[temp[0]] = temp[1]

        # Grab the creation and modification times:
        other_parms = ibw_wave.get('wave_header')
        for key in ['creationDate', 'modDate', 'bname']:
            try:
                parm_dict[key] = other_parms[key]
            except KeyError:
                pass
        wh_idx =  [ind for ind in range(len(parm_list)) if 'Width' in parm_list[ind]][0]
        lines_img_idx = [ind for ind in range(len(parm_list)) if 'lines per image' in parm_list[ind]][0]
        channel_idx = [ind for ind in range(len(parm_list)) if 'Channel name' in parm_list[ind]][0]
        spec_lines_idx = [ind for ind in range(len(parm_list)) if 'Spectroscopy points' in parm_list[ind]][0]

        parm_dict['image_width'] = float(parm_list[wh_idx].split('=')[2][:-3])
        parm_dict['image_height'] = float(parm_list[wh_idx].split('=')[-1][:-3])
        parm_dict['image_units'] = parm_list[wh_idx].split('=')[-1][-3:][1]
        parm_dict['channel_name'] = parm_list[channel_idx].split(':')[1][:-3]
        parm_dict['channel_unit'] = parm_list[channel_idx].split(':')[1][-3:][1]

        if 'Volume CITS' in parm_dict:
            print('this is CITS') 
            sub_grid_idx = [ind for ind in range(len(parm_list)) if 'Scan Sub-Grid' in parm_list[ind]][0]
            spec_curve_idx = [ind for ind in range(len(parm_list)) if 'axis start' in parm_list[ind]][0]
            parm_dict['spec_curve_idx'] = spec_curve_idx
            parm_dict['scan_subgrid_x'] = int(re.findall(r'\d+',parm_list[sub_grid_idx].split('=')[1])[0])
            parm_dict['scan_subgrid_y'] = int(re.findall(r'\d+',parm_list[sub_grid_idx].split('=')[2])[0])
            parm_dict['spec_points_per_line'] =  int(re.findall(r'\d+', parm_list[spec_lines_idx].split('=')[1])[0])
            parm_dict['spec_lines_per_plane'] = int(re.findall(r'\d+', parm_list[spec_lines_idx].split('=')[-1])[0])
            parm_dict['spec_points_per_curve'] = int(parm_list[spec_curve_idx].split('curve =')[1].split(',')[0])
            parm_dict['lines_img_idx'] = parm_list[lines_img_idx]
            parm_dict['datatype'] = 'Volume CITS'    
            
        elif 'Image data' in parm_dict:
            print('this is an image')
            parm_dict['lines_img_idx'] = parm_list[lines_img_idx]
            parm_dict['datatype'] = 'image'    
        parm_dict['parm_list'] = parm_list
        parm_dict['other_parms'] = other_parms

        return parm_dict

    @staticmethod
    def _get_chan_labels(ibw_wave, codec='utf-8'):
        """
        Retrieves the names of the data channels and default units

        Parameters
        ----------
        ibw_wave : dictionary
            Wave entry in the dictionary obtained from loading the ibw file
        codec : str, optional
            Codec to be used to decode the bytestrings into Python strings if needed.
            Default 'utf-8'

        Returns
        -------
        labels : list of strings
            List of the names of the data channels
        default_units : list of strings
            List of units for the measurement in each channel
        """
        temp = ibw_wave.get('labels')
        labels = []
        for item in temp:
            if len(item) > 0:
                labels += item
        for item in labels:
            if item == '':
                labels.remove(item)

        default_units = list()
        for chan_ind, chan in enumerate(labels):
            # clean up channel names
            if type(chan) == bytes:
                chan = chan.decode(codec)
            if chan.lower().rfind('trace') > 0:
                labels[chan_ind] = chan[:chan.lower().rfind('trace') + 5]
            else:
                labels[chan_ind] = chan
            # Figure out (default) units
            if chan.startswith('Phase'):
                default_units.append('deg')
            elif chan.startswith('Current'):
                default_units.append('A')
            else:
                default_units.append('m')

        return labels, default_units

class IgorIBWReader(Reader):
    """
    Extracts data and metadata from Igor Binary Wave (.ibw) files containing
    images or force curves
    """
    def __init__(self, file_path, *args, **kwargs):
        if bw == None:
            raise ModuleNotFoundError('You attempted to load an Igor file, but this requires igor.\n \
            Please Load it with pip install igor , restart and retry')

        super().__init__(file_path, *args, **kwargs)

    def read(self, verbose=False, parm_encoding='utf-8'):
        """
        Reads the file given in file_path into a sidpy dataset

        Parameters
        ----------
        verbose : Boolean (Optional)
            Whether or not to show  print statements for debugging
        parm_encoding : str, optional
            Codec to be used to decode the bytestrings into Python strings if
            needed. Default 'utf-8'

        Returns
        -------
        sidpy.Dataset : List of sidpy.Dataset objects.
            Multi-channel inputs are separated into individual dataset objects
        """
        file_path = self._input_file_path

        # Load the ibw file first
        ibw_obj = bw.load(file_path)
        ibw_wave = ibw_obj.get('wave')
        parm_dict = self._read_parms(ibw_wave, parm_encoding)
        chan_labels, chan_units = self._get_chan_labels(ibw_wave, parm_encoding)
        self.parm_dict =  parm_dict

        if verbose:
            print('Channels and units found:')
            print(chan_labels)
            print(chan_units)
            print('Parameters dictionary:')
            print(parm_dict)

        # Get the data to figure out if this is an image or a force curve
        images = ibw_wave.get('wData')

        datasets = [] #list of sidpy datasets

        if images.shape[-1] != len(chan_labels):
            chan_labels = chan_labels[1:]  # for layer 0 null set errors in older AR software
            chan_units = chan_units[1:]

        if images.ndim == 3:  # Image stack
            if verbose:
                print('Found image stack of size {}'.format(images.shape))

            num_rows = parm_dict['ScanLines']
            num_cols = parm_dict['ScanPoints']

            for channel in range(images.shape[-1]):
                #Convert it to sidpy dataset object
                data_set = sid.Dataset.from_array(images[:,:,channel], name=chan_labels[channel])
                data_set.data_type = 'Image'

                #Add quantity and units
                data_set.units = chan_units[channel]
                data_set.quantity = chan_labels[channel]

                #Add dimension info
                data_set.set_dimension(0, sid.Dimension(np.linspace(0, parm_dict['FastScanSize'], num_cols),
                                                        name = 'x',
                                                        units=chan_units[channel], quantity = 'x',
                                                        dimension_type='spatial'))
                data_set.set_dimension(1, sid.Dimension(np.linspace(0, parm_dict['SlowScanSize'], num_rows),
                                                        name = 'y',
                                                        units=chan_units[channel], quantity='y',
                                                        dimension_type='spatial'))

                # append metadata
                data_set.original_metadata = parm_dict
                data_set.data_type = 'image'

                #Finally, append it
                datasets.append(data_set)

        else:  # single force curve
            if verbose:
                print('Found force curve of size {}'.format(images.shape))

            images = np.atleast_3d(images)  # now [Z, chan, 1]

            # Find the channel that corresponds to either Z sensor or Raw:
            try:
                chan_ind = chan_labels.index('ZSnsr')
                spec_data = images[:,chan_ind].squeeze()
            except ValueError:
                try:
                    chan_ind = chan_labels.index('Raw')
                    spec_data = images[:,chan_ind,0].squeeze()
                except ValueError:
                    # We don't expect to come here. If we do, spectroscopic values remains as is
                    spec_data = np.arange(images.shape[2])

            #Go through the channels
            for channel in range(images.shape[-2]):

                # The data generated above varies linearly. Override.
                # For now, we'll shove the Z sensor data into the spectroscopic values.

                #convert to sidpy dataset
                data_set = sid.Dataset.from_array((images[:,channel,0]), name=chan_labels[channel])

                if verbose:
                    print('Channel {} and spec_data is {}'.format(channel, spec_data))

                #Set units, quantity
                data_set.units = chan_units[channel]
                data_set.quantity = chan_labels[channel]

                data_set.set_dimension(0, sid.Dimension(spec_data, name = chan_labels[channel],
                                                        units=chan_units[channel], quantity=chan_labels[channel],
                                                        dimension_type='spectral'))

                #append metadata
                data_set.data_type = 'SPECTRUM'
                data_set.original_metadata = parm_dict

                #Add dataset to list
                datasets.append(data_set)

        # Return the dataset
        return datasets

    @staticmethod
    def _read_parms(ibw_wave, codec='utf-8'):
        """
        Parses the parameters in the provided dictionary

        Parameters
        ----------
        ibw_wave : dictionary
            Wave entry in the dictionary obtained from loading the ibw file
        codec : str, optional
            Codec to be used to decode the bytestrings into Python strings if needed.
            Default 'utf-8'

        Returns
        -------
        parm_dict : dictionary
            Dictionary containing parameters
        """
        parm_string = ibw_wave.get('note')
        if type(parm_string) == bytes:
            try:
                parm_string = parm_string.decode(codec)
            except:
                parm_string = parm_string.decode('ISO-8859-1')  # for older AR software
        parm_string = parm_string.rstrip('\r')
        parm_list = parm_string.split('\r')
        parm_dict = dict()
        for pair_string in parm_list:
            for split_parm in [':', '=']:
                temp = pair_string.split(split_parm)
                if len(temp) == 2:
                    temp = [item.strip() for item in temp]
                    try:
                        num = float(temp[1])
                        parm_dict[temp[0]] = num
                        try:
                            if num == int(num):
                                parm_dict[temp[0]] = int(num)
                        except OverflowError:
                            pass
                    except ValueError:
                        parm_dict[temp[0]] = temp[1]

        # Grab the creation and modification times:
        other_parms = ibw_wave.get('wave_header')
        for key in ['creationDate', 'modDate', 'bname']:
            try:
                parm_dict[key] = other_parms[key]
            except KeyError:
                pass
        return parm_dict

    @staticmethod
    def _get_chan_labels(ibw_wave, codec='utf-8'):
        """
        Retrieves the names of the data channels and default units

        Parameters
        ----------
        ibw_wave : dictionary
            Wave entry in the dictionary obtained from loading the ibw file
        codec : str, optional
            Codec to be used to decode the bytestrings into Python strings if needed.
            Default 'utf-8'

        Returns
        -------
        labels : list of strings
            List of the names of the data channels
        default_units : list of strings
            List of units for the measurement in each channel
        """
        temp = ibw_wave.get('labels')
        labels = []
        for item in temp:
            if len(item) > 0:
                labels += item
        for item in labels:
            if item == '':
                labels.remove(item)

        default_units = list()
        for chan_ind, chan in enumerate(labels):
            # clean up channel names
            if type(chan) == bytes:
                chan = chan.decode(codec)
            if chan.lower().rfind('trace') > 0:
                labels[chan_ind] = chan[:chan.lower().rfind('trace') + 5]
            else:
                labels[chan_ind] = chan
            # Figure out (default) units
            if chan.startswith('Phase'):
                default_units.append('deg')
            elif chan.startswith('Current'):
                default_units.append('A')
            else:
                default_units.append('m')

        return labels, default_units

    def can_read(self):
        """
        Tests whether or not the provided file has a .ibw extension
        Returns
        -------

        """

        return super(IgorIBWReader, self).can_read(extension='ibw')
