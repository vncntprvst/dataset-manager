#################################################################
# CONTACT DUANE RINEHART (drinehart@ucsd.edu) WITH ANY QUESTIONS
# LAST EDIT: 4-JUN-2025
#################################################################

import os, sys
import re
import argparse
import pandas as pd
from datetime import datetime
from dateutil.tz import tzlocal
from pathlib import Path
import glob
import uuid
import h5py
import numpy as np

from pynwb.image import GrayscaleImage

from pynwb import NWBFile, NWBHDF5IO, H5DataIO
from pynwb.ophys import (
    OpticalChannel,
    TwoPhotonSeries,
)
from hdmf.data_utils import DataChunkIterator

parent = Path(__file__).parents[1] #2 levels up
sys.path.append(parent)
print(f'USING PARENT PATH REFERENCES FOR IMPORTS: {parent}')

sys.path.insert(1, 'lib')
import utils



#################################################################
# APP CONSTANTS (DEFAULT)
# input_path = Path('/', 'net', 'birdstore')
# output_path = Path('/', 'data', 'nwb_tmp')
input_path = Path('/', 'mnt', 'd', 'temp')
output_path = Path('/', 'mnt', 'd', 'temp', 'nwb_tmp')
experiment_modality = 3 #2P (FOR COMPATIBILITY)
experiment_modality_text = 'Volumetric Imaging (2P)'
experiment_description = None #string or null
researcher_experimenter = ""
institution = "UCSD"
performance_lab = 'Kleinfeld Lab'
debug = True
#################################################################


def displayMenu():
    print("*"*40)
    print('-NIH DATA INGESTION COMMAND LINE INTERFACE-')
    print("*"*40)
    print('H5 TO NWB\n')
    print('SEE REPOSITORY (https://github.com/USArhythms/ingestion_scripts) OR EVALUATE CODE FOR USAGE DETAILS\n')
    print('CONTACT DUANE RINEHART (drinehart@ucsd.edu) WITH ANY QUESTIONS\n')
    print("*"*40)


def collectArguments():
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-i", "--input_file", help="Input file (.xlsx) containing experimental parameters/data locations", default="input.xlsx")
    argParser.add_argument("-o", "--output_path", help="Output folder/path where converted nwb files will be stored", default=output_path)
    argParser.add_argument("-exp", "--experiment_modality", help="Valid experiment modes: 1=ephys, 2=widefield, 3=2Photon, 4=fMRI")
    argParser.add_argument("-researcher", "--researcher_experimenter", help="Name(s) of researcher/experimenter", default=researcher_experimenter)
    argParser.add_argument("-institution", "--institution", help="Name of institution", default=institution)
    argParser.add_argument("-debug", "--debug", help="Display debug information", default=False)
    args = argParser.parse_args()
    return args


def displayParam(args, cnt_sessions):
    print("*"*40)
    print("USING THE FOLLOWING PARAMETERS:")
    print(f'SRC (INPUT) META-DATA LOCATION: {args.input_file} [ABSOLUTE PATH OR PATH RELATIVE TO CURRENT DIRECTORY]')
    print(f'DEST (OUTPUT) FILES LOCATION: {args.output_path} [ABSOLUTE PATH OR PATH RELATIVE TO CURRENT DIRECTORY]')
    print(f'SESSIONS IN EXCEL FILE: {cnt_sessions}')
    print("*" * 40)


def load_data(input_file, experiment_modality):
    '''Used for meta-data loading'''
    exp_modality_specific_fields = []
    
    commonFields = ['session_id',
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
                    'experimenters',
                    'institution',
                    'identifier'
                    ]
    
    if experiment_modality == "3":#2photon
        exp_modality_specific_fields = [
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
        ]
    
    #APPEND EXPERIMENT MODALITY SPECFIC FIELDS TO COMMON LIST
    lstNWBFields = commonFields + exp_modality_specific_fields

    matched_fields = []
    try:
        lstExtractionFields = pd.read_excel(input_file, sheet_name="auto", usecols=lstNWBFields) #just extract columns/fields I need
        matched_fields = lstNWBFields
    except ValueError:
        lstExtractionFields = pd.read_excel(input_file, sheet_name="auto")  # read fine 'as is'

        fields_in_file = lstExtractionFields.columns.tolist()
        matched_fields = list(set(fields_in_file).intersection(lstNWBFields))

        print(f"IMPORT WARNING [SOME FIELDS NOT MATCHED] - NWB FIELD COUNT {len(lstNWBFields)}; IMPORT SHEET FIELD COUNT {len(fields_in_file)}")
    finally:
        print(f"SCRIPT WILL CONTINUE WITH THE FOLLOWING FIELDS: {matched_fields}")
        print("*" * 40)

    return lstExtractionFields
    

def main():
    displayMenu()
    if len(sys.argv) > 1:
        args = collectArguments()
        print("USING CLI ARGUMENTS")
    else:
        print("MISSING ARGUMENTS; USING DEFAULTS")
        print(f'\'python {os.path.basename(__file__)} -h\' FOR HELP\n')
        args.output_path = output_path
        args.experiment_modality = experiment_modality
        args.researcher_experimenter = researcher_experimenter
        args.institution = institution
        args.debug = debug
    
    lstRecords = load_data(args.input_file, args.experiment_modality)
    cnt_sessions = lstRecords['session_id'].notna().sum()
    displayParam(args, cnt_sessions)

    ##################################################################################
    #RENAME EXCEL/DATAFRAME FIELD COLUMN NAMES FOR EASIER NWB CONVERSION
    lstRecords.rename(columns={'session_start_time(YYYY-MM-DD HH:MM)': 'session_start_time'}, inplace=True)
    lstRecords.rename(columns={'date_of_birth(YYYY-MM-DD)': 'date_of_birth'}, inplace=True)
    lstRecords.rename(columns={'age(days)': 'age_days'}, inplace=True)
    ##################################################################################

    for cnt, row in enumerate(lstRecords.itertuples(index=False)):
        if pd.isna(row.session_id) or str(row.session_id) == '':
            continue
        print(f"PROCESSING DATASET #{cnt + 1}")
        unique_identifier = str(uuid.uuid4())            
        session_id = str(row.session_id) + "_" + unique_identifier

        session_start_time = row.session_start_time

        if isinstance(session_start_time, pd.Timestamp):
            if pd.isna(session_start_time):
                session_start_time = datetime.now(tzlocal())
            elif session_start_time.tzinfo is None:
                session_start_time = session_start_time.tz_localize(tzlocal())
        elif isinstance(session_start_time, str):
            if not session_start_time:
                session_start_time = datetime.now(tzlocal())
            else:
                session_start_time = pd.to_datetime(session_start_time)
            if session_start_time.tzinfo is None:
                session_start_time = session_start_time.tz_localize(tzlocal())

        ##################################################################################
        # CREATE EXPERIMENTAL SUBJECT OBJECT
        age = row.age_days
        subject_description = row.subject_description
        genotype = row.genotype
        sex = row.sex
        subject_id = row.subject_id
        subject_weight = row.subject_weight
        date_of_birth = row.date_of_birth
        subject_strain = row.subject_strain
        species = row.species

        subject = utils.get_subject(age,
                                    subject_description,
                                    genotype,
                                    sex,
                                    species,
                                    subject_id,
                                    subject_weight,
                                    date_of_birth,
                                    subject_strain)
        ##################################################################################

        keywords = ['Researcher(s): ' + str(row.experimenters)]
        institution = row.institution
        performance_lab = row.performance_lab
        session_description = row.session_description
        researcher_experimenter = row.experimenters
        
        nwbfile = NWBFile(
                session_description=str(session_description),
                identifier=session_id,
                session_start_time=session_start_time,
                keywords = keywords,
                experimenter = researcher_experimenter,
                institution = institution,
                lab = performance_lab,
                subject=subject
            )


        ##################################################################################
        # CONVERT H5 FILE TO NWB
        ##################################################################################
        data_src = Path(str(row.recordings_folder_directory), str(row.analysis_file))
        if debug:
            print(f'DEBUG: Converting file to NWB: {data_src}')

        output_file = Path(args.output_path, Path(data_src).stem + '.nwb')
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(data_src, 'r') as fh:
            dataset = fh['data']
            chunk_iter = DataChunkIterator(dataset, buffer_size=2000)
            data_io = H5DataIO(chunk_iter, compression='gzip')

        ##################################################################################
        #ADD VOLUMETRIC IMAGING ACQUISITION META-DATA
        ##################################################################################
        grayscale_image = GrayscaleImage(
            name='my_grayscale_image',
            data=data_io,
            description='Grayscale image from .h5'
        )

        nwbfile.add_acquisition(grayscale_image)

        # device = nwbfile.create_device(
        #     name=str(row.device_name),
        #     description=str(row.device_description),
        #     manufacturer=str(row.device_manufacturer),
        #     model_number="",
        #     model_name="",
        #     serial_number="",
        # )
        # optical_channel_1 = OpticalChannel(
        #                     name="CH1",
        #                     description="Second harmonic generation (SHG) channel; Imaging Description: Skull; Indicator: SHG",
        #                     emission_lambda=475.0)

        # optical_channel_2 = OpticalChannel(
        #                     name="CH2",
        #                     description="Fluorescein channel; Imaging Description: Vasculature: Indicator: Fluorescein",
        #                     emission_lambda=525.0)

        # imaging_plane = nwbfile.create_imaging_plane(
        #     name="ImagingPlane",
        #     optical_channel=[optical_channel_1, optical_channel_2],
        #     # imaging_rate=30.0,
        #     description="",
        #     device=device,
        #     excitation_lambda=950.0,
        #     indicator="CH1: GFP; CH2: Fluorescein",
        #     location="whole craniocerebral system",
        #     # grid_spacing=[0.01, 0.01],
        #     # grid_spacing_unit="meters",
        #     # origin_coords=[1.0, 2.0, 3.0],
        #     # origin_coords_unit="meters",
        # )

        # two_p_series = TwoPhotonSeries(
        #         name="TwoPhotonSeries",
        #         description="Stitched 2p data; check data for actual rate",
        #         data=data_io,
        #         imaging_plane=imaging_plane,
        #         rate=1.0,
        #         unit="a.u.",
        #     )
        # nwbfile.add_acquisition(two_p_series)
        
        if debug:
            print(f'DEBUG: Output file path: {output_file}')
        with NWBHDF5IO(output_file, 'w') as io:
            io.write(nwbfile)

        print(f"Conversion completed. NWB file saved to {output_file}")
        

if __name__ == "__main__":
    main()