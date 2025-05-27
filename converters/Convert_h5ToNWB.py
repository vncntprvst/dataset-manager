#################################################################
# CONTACT DUANE RINEHART (drinehart@ucsd.edu) WITH ANY QUESTIONS
# LAST EDIT: 27-MAY-2025
#################################################################

import os, sys
import re
import argparse
from datetime import datetime
from dateutil.tz import tzlocal
from pathlib import Path
import glob
import uuid
import h5py
import numpy as np

from pynwb import NWBFile, NWBHDF5IO
from pynwb.ophys import (
    OpticalChannel,
    TwoPhotonSeries,
)

parent = Path(__file__).parents[1] #2 levels up
sys.path.append(parent)
print(f'USING PARENT PATH REFERENCES FOR IMPORTS: {parent}')

sys.path.insert(1, 'lib')
import utils



#################################################################
# APP CONSTANTS (DEFAULT)
input_path = Path('/', 'net', 'birdstore')
output_path = Path('/', 'data', 'tmp')
experiment_modality = 3 #2P (FOR COMPATIBILITY)
experiment_modality_text = '2Photon Imaging'
experiment_description = None #string or null
researcher_experimenter = "Ji, Xiang; Huang, Sincheng"
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


def displayParam(args, files_count):
    print("*"*40)
    print("USING THE FOLLOWING PARAMETERS:")
    print(f'SRC (INPUT) FILES LOCATION: {args.input_path} [ABSOLUTE PATH OR PATH RELATIVE TO CURRENT DIRECTORY]')
    print(f'DEST (OUTPUT) FILES LOCATION: {args.output_path} [ABSOLUTE PATH OR PATH RELATIVE TO CURRENT DIRECTORY]')
    print(f'NUMBER OF H5 FILES FOUND: {files_count}')
    print("*"*40)

    print(f'RESEARCHER/EXPERIMENTER (TERMINAL ARGUMENT): {args.researcher_experimenter}\n')

    if args.institution:
        institution = args.institution
        print(f'INSTITUTION (TERMINAL ARGUMENT): {institution}\n')
    print("*" * 40)


def load_data(input_file, experiment_modality):
    '''Used for meta-data loading'''
    
    #INSPECT H5 FILE FOR META-DATA
    with h5py.File(input_file, 'r') as f:
        meta_data = list(f.keys())

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
    
    matched_fields = commonFields
    lstExtractionFields = matched_fields
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
    
    args.input_path = Path(input_path, 'Vessel', 'WBIM', 'Processing', 'Ablation_test', 'WBIM20240305002_20240801', 'render_v2')
    h5_files = glob.glob(str(Path(args.input_path, '*.h5')))
    pattern = re.compile(r'.*/Ablation_test[^/]*\.h5$')
    ablation_files = [f for f in h5_files if pattern.match(f)]
    displayParam(args, len(ablation_files))
    
    #PROCESS FILES
    if ablation_files:
        for file in ablation_files:
            if debug:
                print(f'DEBUG: Processing file: {file}')
            lstRecords = load_data(file, args.experiment_modality) #TODO: ADD EXTRACTION FROM EXCEL FILE, IF META-DATA NOT EMBEDDED IN H5 FILE
            
            identifier = str(uuid.uuid4())
            desc = str(Path(file).stem)
            session_start_time = ''
            
            if not session_start_time:
                session_start_time = datetime.now(tzlocal())
            elif session_start_time.tzinfo is None:
                session_start_time = session_start_time.replace(tzinfo=tzlocal())

            age = subject_description = genotype = sex = species = subject_id = subject_weight = date_of_birth = subject_strain = ''
            ##################################################################################
            # CREATE EXPERIMENTAL SUBJECT OBJECT
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

            keywords = ['Researcher(s): ' + str(researcher_experimenter)]

            # with h5py.File(file, 'r') as fh:
            #     data = fh['data'][:]
            data = np.ones((1000, 100, 100))
            
            nwbfile = NWBFile(
                session_description=desc,
                identifier=identifier,
                session_start_time=session_start_time,
                keywords = keywords,
                experimenter = researcher_experimenter,
                institution = institution,
                lab = performance_lab,
                subject=subject
            )

            device = nwbfile.create_device(
                name="Microscope",
                description="2 photon microscope",
                manufacturer="",
                model_number="",
                model_name="",
                serial_number="",
            )
            optical_channel = OpticalChannel(
                name="OpticalChannel",
                description="CH1",
                emission_lambda=500.0,
            )
            imaging_plane = nwbfile.create_imaging_plane(
                name="ImagingPlane",
                optical_channel=optical_channel,
                imaging_rate=30.0,
                description="a very interesting part of the brain",
                device=device,
                excitation_lambda=600.0,
                indicator="GFP",
                location="V1",
                grid_spacing=[0.01, 0.01],
                grid_spacing_unit="meters",
                origin_coords=[1.0, 2.0, 3.0],
                origin_coords_unit="meters",
            )
            two_p_series = TwoPhotonSeries(
                name="TwoPhotonSeries",
                description="Raw 2p data",
                data=data,
                imaging_plane=imaging_plane,
                rate=1.0,
                unit="normalized amplitude",
            )

            nwbfile.add_acquisition(two_p_series)
            
            output_file = Path(args.output_path, Path(file).stem + '.nwb')
            if debug:
                print(f'DEBUG: Output file path: {output_file}')
            with NWBHDF5IO(output_file, 'w') as io:
                io.write(nwbfile)

            print(f"Conversion completed. NWB file saved to {output_file}")
            
    else:
        print("NO H5 FILES FOUND; EXITING")
        sys.exit(1)

if __name__ == "__main__":
    main()