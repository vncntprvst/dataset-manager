# CREATED: 4-MAY-2024
# LAST EDIT: 8-MAY-2023
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''METHODS/FUNCTIONS FOR PROCESSING BEHAVIOR EXPERIMENTAL MODALITY'''

import os
from pathlib import Path, PurePath
import shutil
from scipy.io import loadmat
import numpy as np
import pandas as pd
from pynwb.behavior import TimeSeries, BehavioralTimeSeries


def get_video_reference_data(src_file_with_path, nwb_folder_directory, symbolic_link=False):
    '''
    Used to process external video file data

    :param src_folder_directory: location of external video file (absolute path)
    :param nwb_folder_directory: location of nwb file (absolute path)
    :param symbolic_link: determines if symbolic link will be created pointing to org file (default is false but file will be copied to staging directory if set to True)
    :return: relative reference to video file [relative to nwb location]
    '''

    output_path_stub = nwb_folder_directory.parts[:-1]
    ext_files_path = Path(*output_path_stub, 'external_files')
    Path(ext_files_path).mkdir(parents=True, exist_ok=True)

    src_filename = os.path.basename(os.path.normpath(src_file_with_path))
    dest_file_with_path = Path(ext_files_path, src_filename)

    if os.path.exists(src_file_with_path):
        try:
            print('\tATTEMPTING TO CREATE SYMBOLIC LINK')
            #NOTE SYMBOLIC LINK CREATION PERMISSIONS MAY BE RESTRICTED ON WINDOWS PLATFORM [NOT WORKING AS OF 1-MAY-2023]
            #WINDOWS 11 MUST BE IN 'DEVELOPER MODE' TO ENABLE SYMBOLIC LINK CREATION
            #ref: https://learn.microsoft.com/en-us/windows/apps/get-started/developer-mode-features-and-debugging#additional-developer-mode-features

            # winplatform = utils.IsWin11()
            # print("here")
            # if winplatform is True:
            #
            #     cmd = f'New-Item -ItemType SymbolicLink -Path "{dest_file_with_path}" -Target "{src_file_with_path}"'
            #     print('SCRIPT NON-FUNCTION ON WINDOWS 11 AS OF 1-MAY-2023')
            # else:

            #ONLY LINUX SUPPORTED AS OF 1-MAY-2023
            if os.path.realpath(dest_file_with_path) != src_file_with_path:
                os.symlink(src_file_with_path, dest_file_with_path)
                print(f'\tSYMLINK CREATED:{src_file_with_path, dest_file_with_path}')
            else:
                print(f'\tSYMLINK EXISTS')
        except:
            print('\tATTEMPTING TO COPY FILE - ONLY IF SYMBOLIC LINK CREATION FAILS')
            shutil.copy2(src_file_with_path, ext_files_path)
    else:
        print(f'UNABLE TO PROCESS VIDEO [REFERENCE] FILE: {src_filename}')

    #print(f'src: {ext_files_path, os.path.dirname(nwb_folder_directory)}')
    rel_path_to_nwb_file_location = Path(os.path.relpath(ext_files_path, os.path.dirname(nwb_folder_directory)), src_filename)
    return rel_path_to_nwb_file_location


def extract_img_series_data(mat_file):
    '''EXTRACT/COMPILE COMMENTS FOR IMAGE SERIES'''
    img_comments = ''
    titles = ['a', 'b', 'phi', 'X0', 'Y0', 'X0_in', 'Y0_in', 'long_axis', 'short_axis']

    if Path(mat_file).is_file():
        param = loadmat(mat_file)['ellipse_params'].tolist()

        for i in range(9):
            var_name = titles[i]
            var_val = str(param[0][0][i][0][0])
            img_comments += var_name + ':' + var_val + '; '
    else:
        print(f'\tCOMMENTS FOR VIDEO FILE NOT INCLUDED')
    return img_comments


def add_timeseries_data(file, video_sampling_rate_Hz, name, description):
    '''READ FILE, EXTRACT NDARRAY INFO AND CREATE NWB-COMPATIBLE OBJECT
       COMPATIBLE WITH EXCEL (.xlsx) AND MATLAB (.mat)
    '''

    file_extension = Path(file).suffix

    unit = 'NA'

    if file_extension == '.xlsx':
        nd_array_timeseries_data = pd.read_excel(file).to_numpy()
    else:
        nd_array_timeseries_data = loadmat(file)['data']  # get just the ndarray part

        if nd_array_timeseries_data.shape[0] == 1:
            nd_array_timeseries_data = nd_array_timeseries_data.T

        if name == 'raw_labchart_data':
            for datastart, dataend in zip(loadmat(file)['datastart'], loadmat(file)['dataend']):
                unit += "({},{}) ".format(str(int(datastart)), str(int(dataend)))


    speed_time_series = TimeSeries(
        name=name,
        data=nd_array_timeseries_data,
        rate = video_sampling_rate_Hz, #float
        description=description,
        unit=unit
    )
    behavioral_time_series = BehavioralTimeSeries(
        time_series=speed_time_series,
        name="BehavioralTimeSeries",
    )
    return behavioral_time_series


def add_matrix_data(file, name, description):
    '''NOT REALLY TIMESERIES, JUST A HACK TO ADD MATRIX DATA TO NWB CONTAINER'''

    file_extension = Path(file).suffix

    if file_extension == '.csv': #processing
        csv_data = pd.read_csv(file)
        data = np.array((csv_data.columns.tolist(), csv_data.iloc[0, :].values.tolist())).T
    else: #analysis (.mat)
        bools = loadmat(file)['bBoolsMat']
        data = bools

    unit = 'NA'
    container = TimeSeries(
        name=name,
        data=data,
        rate=0.0,  # float
        description=description,
        unit=unit
    )
    data = BehavioralTimeSeries(
        time_series=container,
        name=name
    )
    return data


def add_str_data(file, name):

    df = pd.read_csv(file)

    data = ','.join(df.columns) + '|'

    if name == 'notes':

        for i in range(df.shape[0]):
            row = df.iloc[i].values.tolist()
            row[1], row[2] = str(row[1]), str(row[2])
            data += ','.join(row) + ' | '

    elif name == 'stimulus_notes':

        for i in range(df.shape[0]):
            row = [str(x) for x in df.iloc[i].values.tolist()]
            data += ','.join(row) + ' | '


    return data