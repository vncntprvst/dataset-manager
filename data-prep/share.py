# CREATED: 14-FEB-2023
# LAST EDIT: 11-APR-2023
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''IMPLEMENTS INTERFACE BETWEEN LOCAL EXPERIMENTAL DATA (AND META-DATA) AND REMOTE DATA SHARING PORTAL FOR U19 GRANT INSTITUTIONS'''

import os, sys, math, time, pynwb
from pynwb.ophys import OpticalChannel, TwoPhotonSeries, ImagingPlane
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from pathlib import Path
from ast import literal_eval
import tifffile

#################################################################
# APP CONSTANTS (DEFAULT)
output_path = Path(os.getcwd(), 'output')
# debug = True

experimenter = 'Yao, Pantong'
institution = 'UC San Diego'
experiment_description = None #string or null
keywords = ['Researchers: ' + str(experimenter)]
#################################################################

def displayMenu():
    print('DATA SHARING COMMAND LINE INTERFACE\n')


def collectArguments():
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-i", "--input_file", help="Input file (.xlsx) containing experimental parameters/data locations")
    args = argParser.parse_args()
    return args


def displayParam(args):
    print("*"*40)
    print("USING THE FOLLOWING PARAMETERS:\n")
    print(f'INPUT FILE: {args.input_file} [PATH RELATIVE TO CURRENT DIRECTORY]\n')
    print(f'OUTPUT FOLDER: {output_path}')
    print("*" * 40)


def load_data(input_file):
    '''Used for meta-data loading'''
    lstNWBFields = [
        'session_id',
        'subject_id',
        'age',
        'subject_description',
        'genotype',
        'sex',
        'species',
        'subject_weight',
        'subject_strain',
        'date_of_birth(YYYY-MM-DD)',
        'session_description',
        'src_folder_directory',
        'stimulus_notes_include',
        'stimulus_notes_paradigm',
        'stimulus_notes_direct_electrical_stimulation',
        'stimulus_notes_direct_electrical_stimulation_paradigm',
        'pharmacology_notes_anesthetized_during_recording',
        'pharmacology',
        'anesthesia_acute_chronic',
        'anesthesia_chronic_days_post_admin',
        'device_name',
        'device_description',
        'device_manufacturer',
        'optical_channel_name',
        'optical_channel_description',
        'optical_channel_emission_lambda',
        'image_stack_name',
        'image_stack_imaging_rate',
        'image_stack_description',
        'image_stack_exitation_lambda',
        'image_stack_indicator',
        'image_stack_location',
        'image_stack_grid_spacing',
        'image_stack_grid_spacing_unit'
    ]  # headers I need

    lstExtractionFields = pd.read_excel(input_file, sheet_name="auto", usecols=lstNWBFields) #just extract columns/fields I need
    return lstExtractionFields


def get_subject(age, subject_description, genotype, sex, species, subject_id, subject_weight, date_of_birth, subject_strain):
    '''Used for meta-data '''
    if isinstance(age, str) != True:
        try:
            subject_age = "P" + str(int(age)) + "D" #ISO 8601 Duration format - assumes 'days'
        except:
            subject_age = "P0D" #generic

    dob = date_of_birth.to_pydatetime() #convert pandas timestamp to python datetime format
    if isinstance(dob.year, int) and isinstance(dob.month, int) and isinstance(dob.day, int) == True:
        date_of_birth = datetime(dob.year, dob.month, dob.day, tzinfo=tzlocal())
    else:
        date_of_birth = None

    subject = pynwb.file.Subject(age=subject_age,
                             description=subject_description,
                             genotype=str(genotype),
                             sex=sex,
                             species=species,
                             subject_id=subject_id,
                             weight=subject_weight,
                             date_of_birth=date_of_birth,
                             strain=subject_strain
                            )
    return subject


def main():
    displayMenu()
    if len(sys.argv) > 1:
        args = collectArguments()
        displayParam(args)

        lstRecords = load_data(args.input_file).to_dict('records')  # creates list of dictionaries

        for cnt, dataset in enumerate(lstRecords):
            print(f"PROCESSING DATASET #{cnt + 1}")
            print(f"\tsession_id: {dataset['session_id']}")
            age = dataset['age']
            subject_description = dataset['subject_description']
            genotype = dataset['genotype']
            if dataset['sex'] == 'Male':
                sex = 'M'
            elif dataset['sex'] == 'Female':
                sex = 'F'
            else:
                sex = 'U'  # unknown
            species = dataset['species']
            subject_id = dataset['subject_id']
            subject_weight = dataset['subject_weight']
            date_of_birth = dataset['date_of_birth(YYYY-MM-DD)']
            subject_strain = dataset['subject_strain']

            ##################################################################################
            # CREATE EXPERIMENTAL SUBJECT OBJECT
            subject = get_subject(age,
                                  subject_description,
                                  genotype,
                                  sex,
                                  species,
                                  subject_id,
                                  subject_weight,
                                  date_of_birth,
                                  subject_strain)
            ##################################################################################

            ##################################################################################
            output_filename = None
            session_id = dataset['session_id']
            filename = Path(session_id)  # wrong extension; replace with 'nwb'
            output_filename = filename.with_suffix('.nwb')
            dest_path = Path(output_path, output_filename)

            Path(output_path).mkdir(parents=True, exist_ok=True)

            print(f'\tOUTPUT FILE: {dest_path}')

            input_filename = Path(os.getcwd(), dataset['src_folder_directory'])
            print(f'\tINPUT FILE: {input_filename}')
            ##################################################################################

            ##################################################################################
            #CREATE NWB FILE (BASIC META-DATA)
            nwbfile = pynwb.NWBFile(session_description = dataset['session_description'],
                                    identifier = '',  # 1-DEC-2022 mod
                                    session_start_time = datetime(2023, 3, 2, tzinfo=tzlocal()),
                                    experiment_description = experiment_description,
                                    keywords = keywords,
                                    # surgery=None,  # add: Duane 17-NOV-2022
                                    # pharmacology=pharmacology,  # add: Duane 17-NOV-2022
                                    # stimulus_notes=stimulus_notes,  # add: Duane 18-NOV-2022
                                    experimenter = experimenter,
                                    institution = institution,
                                    subject=subject
                                    )

            ##################################################################################
            #ADD CONTAINER TO STORE IMAGE STACK DATA
            device = nwbfile.create_device(
                name = dataset['device_name'],
                description = dataset['device_description'],
                manufacturer = dataset['device_manufacturer']
            )

            #check if optical_channel1 is used
            if str(dataset["optical_channel_name"]) != 'nan':
                optical_channel = OpticalChannel(
                    name = dataset['optical_channel_name'],
                    description = dataset['optical_channel_description'],
                    emission_lambda = float(dataset['optical_channel_emission_lambda'])
                )
                imaging_plane = nwbfile.create_imaging_plane(
                    name = dataset['image_stack_name'],
                    description=dataset['image_stack_description'],
                    device = device,
                    optical_channel = optical_channel,
                    imaging_rate = float(dataset['image_stack_imaging_rate']),
                    excitation_lambda = float(dataset['image_stack_exitation_lambda']),
                    indicator = dataset['image_stack_indicator'],
                    location = dataset['image_stack_location'],
                    grid_spacing = literal_eval(dataset['image_stack_grid_spacing']),
                    grid_spacing_unit = dataset['image_stack_grid_spacing_unit']
                )

            ##################################################################################
            #ADD FILE DATA (IMAGE STACK)



            data = tifffile.imread(input_filename)
            rate = float(dataset['image_stack_imaging_rate'])

            image_series = TwoPhotonSeries(
                name='TwoPhotonSeries',
                data = data,
                imaging_plane=imaging_plane,
                rate=rate,
                unit='NA',
            )

            nwbfile.add_acquisition(image_series)

            ##################################################################################
            #WRITE NWB FILE TO STORAGE
            with pynwb.NWBHDF5IO(dest_path, 'w') as io:
                io.write(nwbfile)

            ##################################################################################

            #VALIDATE .NWB FILE (FOR COMPLIANCE WITH CURRENT SPEC)
            print(f'VALIDATING OUTPUT FILE: {dest_path}')
            #exec(open(f'nwbinspector {dest_path}').read())
            #nwbinspector .. /../ output / run03_airpuff_hindlimb_40psi_200924_155523.nwb - -config
            #dandi


    else:
        print("MISSING ARGUMENTS; UNABLE TO CONTINUE")
        print(f'\'python {os.path.basename(__file__)} -h\' FOR HELP\n')
        exit()


if __name__ == "__main__":
    main()