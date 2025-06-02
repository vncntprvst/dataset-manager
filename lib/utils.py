# CREATED: 27-APR-2023
# LAST EDIT: 30-MAY-2025
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''ADMIN HELPER FUNCTIONS FOR DATA PROCESSING'''

import sys
import re
from datetime import datetime
from dateutil.tz import tzlocal
import pandas as pd
import pynwb.file

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
    
    subject = pynwb.file.Subject(age=subject_age, 
                                 description=subject_description,
                                 genotype=str(genotype),
                                 sex=sex,
                                 species=species,
                                 subject_id=subject_id,
                                 weight=str(subject_weight),
                                 date_of_birth=dob,
                                 strain=subject_strain
                            )
    return subject