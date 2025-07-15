# CREATED: 4-MAY-2024
# LAST EDIT: 14-JUL-2025
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''METHODS/FUNCTIONS FOR PROCESSING BEHAVIOR EXPERIMENTAL MODALITY'''

import os
from pathlib import Path, PurePath
import shutil
from scipy.io import loadmat
from sklearn.preprocessing import LabelEncoder
import numpy as np
import pandas as pd
import h5py
from h5py import Dataset
from pynwb.behavior import TimeSeries, BehavioralTimeSeries, BehavioralEvents


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


def add_timeseries_data(data, video_sampling_rate_Hz, name, description):
    """
    Creates a NWB TimeSeries or BehavioralTimeSeries from various input types.
    Supports:
    - np.ndarray
    - dict (converted from MATLAB structs)
    - .xlsx/.mat files
    - list of 1D NumPy arrays
    - h5py.Dataset
    """
    print(f"Processing data for: {name}")
    unit = 'NA'
    print(f"add_timeseries_data received data of type: {type(data)}")

    if isinstance(data, list):
        print(f"Length: {len(data)}; element types: {[type(d) for d in data[:5]]}")
        # === Fix 1: flatten if list contains a single list ===
        if len(data) == 1 and isinstance(data[0], list):
            print("Flattening nested list of arrays")
            data = data[0]

    # === CASE 0: Dictionary (from MATLAB struct) ===
    if isinstance(data, dict):
        print("Converting dictionary (MATLAB struct) to padded NumPy array")
        
        print(f"Dict keys in '{name}': {list(data.keys())}")
        special_keys = {'bp', 'sglx', 'traj', 'trials', 'me'}
        arrays = []

        for k, v in data.items():
            print(f"  {k}: type={type(v)}, shape={getattr(v, 'shape', 'N/A')}")
            if k in special_keys:
                if isinstance(v, list):
                    print(f"  -> Scanning list from key '{k}'")
                    for i, item in enumerate(v):
                        print(f"    [{k}][{i}]: type={type(item)}, shape={getattr(item, 'shape', 'N/A')}")

                        # Try to convert list-of-lists into ndarray
                        if isinstance(item, list):
                            try:
                                arr = np.asarray(item)
                                print(f"      -> Converted to array: shape={arr.shape}, dtype={arr.dtype}")
                                if arr.ndim <= 2 and np.issubdtype(arr.dtype, np.number):
                                    arrays.append(arr)
                            except Exception as e:
                                print(f"      -> Failed to convert list to array: {e}")

                        # Check for dicts with embedded arrays
                        elif isinstance(item, dict):
                            for subk, subv in item.items():
                                print(f"      [{k}][{i}]['{subk}']: type={type(subv)}, shape={getattr(subv, 'shape', 'N/A')}")
                                if isinstance(subv, np.ndarray) and subv.ndim <= 2:
                                    print(f"        -> Adding array from '{k}[{i}][{subk}]'")
                                    arrays.append(subv)

                        # Direct array
                        elif isinstance(item, np.ndarray):
                            print(f"      -> Direct array: shape={item.shape}")
                            if item.ndim <= 2:
                                arrays.append(item)
                elif isinstance(v, dict):
                    print(f"  -> Scanning nested dict from key '{k}'")
                    for subk, subv in v.items():
                        if isinstance(subv, np.ndarray) and subv.ndim <= 2:
                            arrays.append(subv)

                elif isinstance(v, np.ndarray) and v.ndim <= 2:
                    arrays.append(v)

        if not arrays:
            raise ValueError(f"No usable NumPy arrays found in special keys for '{name}'")

        max_len = max(arr.shape[0] for arr in arrays)
        padded = np.full((len(arrays), max_len), np.nan)

        for i, arr in enumerate(arrays):
            padded[i, :arr.shape[0]] = arr

        nd_array_timeseries_data = padded
        unit += " (padded with NaN)"
    # === CASE 1: NumPy array ===
    if isinstance(data, np.ndarray):
        nd_array_timeseries_data = data

    # === CASE 2: List of 1D arrays ===
    elif isinstance(data, list) and all(isinstance(d, np.ndarray) for d in data):
        try:
            nd_array_timeseries_data = np.stack(data)
        except ValueError:
            max_len = max(d.shape[0] for d in data)
            padded = np.full((len(data), max_len), np.nan)
            for i, d in enumerate(data):
                padded[i, :d.shape[0]] = d
            nd_array_timeseries_data = padded
            unit += " (padded with NaN)"

    # === CASE 3: h5py.Dataset ===
    elif isinstance(data, Dataset):
        nd_array_timeseries_data = data[()].squeeze()

    # === CASE 4: file path (.xlsx, .mat) ===
    elif isinstance(data, (str, bytes, os.PathLike)):
        file = data
        file_extension = Path(file).suffix

        if file_extension == '.xlsx':
            nd_array_timeseries_data = pd.read_excel(file).to_numpy()

        elif file_extension == '.mat':
            mat_data = loadmat(file)
            nd_array_timeseries_data = mat_data['data']
            if nd_array_timeseries_data.shape[0] == 1:
                nd_array_timeseries_data = nd_array_timeseries_data.T

            if name == 'raw_labchart_data':
                for datastart, dataend in zip(mat_data['datastart'], mat_data['dataend']):
                    unit += f"({int(datastart)},{int(dataend)}) "
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

    else:
        raise TypeError(f"Unsupported data type: {type(data)}")

    # === Sanitize ===
    try:
        nd_array_timeseries_data = sanitize_data(nd_array_timeseries_data)
    except ValueError as e:
        if nd_array_timeseries_data.dtype.kind in {'U', 'S', 'O'}:
            flat_data = nd_array_timeseries_data.flatten().astype(str)
            le = LabelEncoder()
            try:
                numeric_data = le.fit_transform(flat_data)
                nd_array_timeseries_data = numeric_data.reshape(nd_array_timeseries_data.shape)
                unit += " (encoded categories)"
            except Exception as err:
                raise ValueError(f"Cannot encode string data in '{name}' to numeric: {err}") from err
        else:
            raise e

    # === Create NWB TimeSeries ===
    timeseries = TimeSeries(
        name=name,
        data=nd_array_timeseries_data,
        rate=float(video_sampling_rate_Hz),
        description=str(description),
        unit=str(unit)
    )

    behavioral_time_series = BehavioralTimeSeries(
        time_series=timeseries,
        name="BehavioralTimeSeries"
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


def sanitize_data(data):
    """
    Attempt to convert messy MATLAB-loaded arrays (possibly with objects or references)
    into a flat numpy float array, filtering out invalid elements.
    """
    arr = np.asarray(data)
    try:
        if isinstance(arr, np.ndarray):
            if arr.dtype.kind in {'U', 'S'}:  # Unicode or byte string
                return np.asarray(arr, dtype=str)
            elif arr.dtype == object:
                flat = []
                for item in arr.flatten():
                    if isinstance(item, (float, int, np.floating, np.integer)):
                        flat.append(item)
                    elif isinstance(item, (list, tuple, np.ndarray)):
                        flat.extend([x for x in np.asarray(item).flatten() if isinstance(x, (float, int))])
                    elif isinstance(item, h5py.Reference):
                        continue  # skip
                    elif isinstance(item, (str, np.str_)):
                        flat.append(str(item))
                # Check if all are strings
                if all(isinstance(x, str) for x in flat):
                    return np.asarray(flat, dtype=str)
                return np.asarray(flat, dtype=float)
            else:
                return np.asarray(arr, dtype=float)
        else:
            # Scalar input
            return np.asarray([arr], dtype=float)
    except Exception as e:
        raise ValueError(f"Cannot convert object array to float or string for NWB TimeSeries: {e}")


def add_behavioral_event_data(event_name: str, events_dict, unit='seconds', description_prefix='Behavioral event timestamps'):
    '''
    #ref: https://pynwb.readthedocs.io/en/stable/pynwb.behavior.html

    Create a BehavioralEvents container with a single TimeSeries representing event timestamps (e.g., licks).

    Parameters
    ----------
    event_name : str
        Name of the behavioral event (e.g., 'lickL', 'lickR').
    event_times : list, np.ndarray
        Timestamps of the events (should be 1D array-like).
    unit : str, optional
        Unit of the timestamps, default is 'seconds'.
    description : str, optional
        Description of the behavioral event time series.

    Returns
    -------
    BehavioralEvents
        A BehavioralEvents object containing the given timestamps as an instantaneous TimeSeries.

    '''
    events = BehavioralEvents(name="BehavioralEvents")

    for sub_event_name, raw in events_dict.items():
        # Flatten nested object arrays
        flattened_times = []

        if isinstance(raw, np.ndarray) and raw.dtype == object:
            for item in raw.flatten():
                if isinstance(item, (float, int, np.floating, np.integer)):
                    flattened_times.append(item)
                elif isinstance(item, (list, np.ndarray)):
                    flattened_times.extend(np.asarray(item).flatten())
                # Skip references, None, etc.
        else:
            flattened_times = np.asarray(raw).flatten()

        # Convert to numpy float array
        try:
            event_times = np.asarray(flattened_times, dtype=float)
        except Exception as e:
            print(f"Skipping {sub_event_name}: can't convert to float – {e}")
            continue

        # Skip if empty or NaN
        if event_times.size == 0 or np.all(np.isnan(event_times)):
            continue

        # Add as instantaneous TimeSeries
        events.create_timeseries(
            name=sub_event_name,
            data=np.ones_like(event_times),
            timestamps=event_times,
            unit='seconds',
            continuity='instantaneous',
            description=f'{description_prefix}: {sub_event_name}'
        )

    return events


def load_cluster_timeseries(ref_array, mat_file):
    """
    Loads each dataset as a 1D NumPy array and returns a list per cluster.
    """
    all_clusters = []
    for i, ref_list in enumerate(ref_array):
        ref_list = np.ravel(ref_list)
        print(f"Cluster {i} contains {len(ref_list)} object references")

        time_series_data = []
        for j, ref in enumerate(ref_list):
            dataset = mat_file[ref]
            if isinstance(dataset, h5py.Dataset):
                data = dataset[()].squeeze()  # convert (N,1) to (N,)
                time_series_data.append(data)
            else:
                raise TypeError(f"Expected h5py.Dataset at ref {j}, got {type(dataset)}")

        all_clusters.append(time_series_data)

    return all_clusters