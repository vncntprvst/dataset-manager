# CREATED: 27-APR-2023
# LAST EDIT: 10-JUL-2025
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''ADMIN HELPER FUNCTIONS FOR DATA PROCESSING'''

import sys
from pathlib import Path
import re
from datetime import datetime
from dateutil.tz import tzlocal
import pandas as pd
import pynwb.file
import scipy.io
import h5py
import numpy as np 
from scipy.io import loadmat
from scipy.io.matlab import mat_struct


def IsWin11():
    if sys.getwindowsversion().build > 22000:return True
    else:return False


def get_subject(age: int, subject_description: str, genotype: str, sex: str, species: str, subject_id, subject_weight, date_of_birth = None, subject_strain: str = None):
    '''Used for meta-data 
    Creates a pynwb.file.Subject object with the provided parameters.
    '''

    subject_age = 'P0D'  # DEFAULT VALUE
    if isinstance(age, int) == True:
        subject_age = "P" + str(int(age)) + "D"  # ISO 8601 Duration format - assumes 'days'
    elif isinstance(age, str) == True and re.search("^P*D$", age):  # STARTS WITH 'P' AND ENDS WITH 'D' (CORRECT FORMATTING)
        subject_age = age
        
    if date_of_birth is not None:
        print(f"date_of_birth: {date_of_birth} ({type(date_of_birth)})")
        if isinstance(date_of_birth, pd.Timestamp):
            dob = date_of_birth.to_pydatetime()
        elif isinstance(date_of_birth, str):
            try:
                dob = datetime.fromisoformat(date_of_birth)
            except ValueError:
                dob = pd.to_datetime(date_of_birth).to_pydatetime()
        else:
            raise TypeError(f"Unsupported type for date_of_birth: {type(date_of_birth)}")
        
        # Normalize to just YMD with local timezone
        try:
            dob = datetime(dob.year, dob.month, dob.day, tzinfo=tzlocal())
        except Exception as e:
            dob = None  # fallback if any error occurs in normalization

    if sex is not None:
        if sex[0].upper() == 'M': #could me 'Male' or just 'M'
            sex_obj = 'M'
        elif sex[0].upper() == 'F' :
            sex_obj = 'F'
    else:
        sex_obj = 'U'  # unknown sex
    
    subject = pynwb.file.Subject(age=str(subject_age), 
                                 description=str(subject_description),
                                 genotype=str(genotype),
                                 sex=sex_obj,
                                 species=species,
                                 subject_id=subject_id,
                                 weight=str(subject_weight),
                                 date_of_birth=dob,
                                 strain=subject_strain
                            )
    return subject


def extract_mat_data_by_key(input_filename: Path, revised_scratch_path: Path):
    '''Extracts data from MATLAB .mat file (v7.3 or old-style v7.2)
    
    Returns:
        - data_dict: dict of top-level keys and their content
        - mat_file: h5py.File handle if using v7.3 (else None)
    '''

    print(f'READING .mat FILE: {input_filename}')
    data_dict = {}

    # === Try modern HDF5-based MAT (v7.3) ===
    try:
        mat_file = h5py.File(input_filename, 'r')  # Will remain open
        print("Loaded as HDF5 (v7.3+) format")

        obj = mat_file['obj']
        for key in obj.keys():
            item = obj[key]
            if isinstance(item, h5py.Group):
                data_dict[key] = {}
                for subkey in item.keys():
                    subitem = item[subkey]
                    if isinstance(subitem, h5py.Group):
                        data_dict[key][subkey] = subitem  # Store Group as-is
                    elif isinstance(subitem, h5py.Dataset):
                        if subitem.dtype == 'object':
                            data_dict[key][subkey] = subitem  # Keep object refs
                        else:
                            data_dict[key][subkey] = np.array(subitem)
            elif isinstance(item, h5py.Dataset):
                data_dict[key] = np.array(item)

        return data_dict, mat_file

    # === Fallback: classic MAT (v7.2 or older) ===
    except (OSError, KeyError) as e:
        print("Falling back to legacy v7.2 MAT format (scipy.io.loadmat)")
        mat_file = None
        mat_data = scipy.io.loadmat(input_filename, struct_as_record=False, squeeze_me=True)

        def _convert_mat_struct(mat_obj):
            """Recursively convert mat_struct to Python dicts."""
            if isinstance(mat_obj, scipy.io.matlab.mio5_params.mat_struct):
                return {field: _convert_mat_struct(getattr(mat_obj, field)) 
                        for field in mat_obj._fieldnames}
            elif isinstance(mat_obj, np.ndarray):
                return [_convert_mat_struct(x) for x in mat_obj]  # Handle arrays of structs
            else:
                return mat_obj  # Return as-is (numeric, string, etc.)

        # Process all top-level keys
        for key in mat_data:
            if not key.startswith('__'):  # Skip MATLAB metadata
                data_dict[key] = _convert_mat_struct(mat_data[key])

        return data_dict, mat_file


def matstruct_to_dict(matobj):
    if isinstance(matobj, np.ndarray):
        return [matstruct_to_dict(o) for o in matobj]
    elif isinstance(matobj, mat_struct):
        result = {}
        for field in matobj._fieldnames:
            value = getattr(matobj, field)
            result[field] = matstruct_to_dict(value)
        return result
    else:
        return matobj


def explore_group(group, prefix=''):
    '''Recursively explores an h5py groupings and prints its structure.
    USED FOR TESTING/DEBUGGING of modern .mat files.'''

    for key in group.keys():
        item = group[key]
        if isinstance(item, h5py.Group):
            print(f"{prefix}{key}/")
            explore_group(item, prefix + key + '/')
        else:
            print(f"{prefix}{key}: {item.shape} {item.dtype}")