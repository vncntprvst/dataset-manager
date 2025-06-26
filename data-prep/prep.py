# CREATED: 11-APR-2023
# LAST EDIT: 6-JUN-2025
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''TERMINAL CONVERSION SCRIPT FOR MULTIPLE EXPERIMENTAL MODALITIES'''

import os, sys, math, pynwb, re, glob
from pathlib import Path, PurePath
import argparse
import pandas as pd
import uuid
from datetime import datetime
from dateutil.tz import tzlocal
from scipy.io import loadmat

from pynwb import NWBHDF5IO, NWBFile
from pynwb.image import ImageSeries

parent = Path(__file__).parents[1] #2 levels up
sys.path.append(parent)
print("*"*40)
print(f'USING PARENT PATH REFERENCES FOR IMPORTS: {parent}')
print("*"*40)
sys.path.insert(1, 'lib')
sys.path.insert(1, 'converters')

import utils
import behavior
from ConvertIntanToNWB import convert_to_nwb

#################################################################
# APP CONSTANTS (DEFAULT)
output_path = Path(os.getcwd(), 'output')
experiment_description = None #string or null
scratch_path = Path('/', 'data', 'nwb_tmp')
debug = True
#################################################################


def displayMenu():
    print("*"*40)
    print('-NIH DATA INGESTION COMMAND LINE INTERFACE-')
    print("*"*40)
    print('SEE REPOSITORY (https://github.com/USArhythms/ingestion_scripts) OR EVALUATE CODE FOR USAGE DETAILS\n')
    print('CONTACT DUANE RINEHART (drinehart@ucsd.edu) WITH ANY QUESTIONS\n')
    print("*"*40)


def collectArguments():
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-i", "--input_file", help="Input file (.xlsx) containing experimental parameters/data locations")
    argParser.add_argument("-o", "--output_path", help="Output folder/path where converted nwb files will be stored")
    argParser.add_argument("-exp", "--experiment_modality", help="Valid experiment modes: 1=ephys, 2=widefield, 3=2Photon, 4=fMRI")
    argParser.add_argument("-researcher", "--researcher_experimenter", help="Name(s) of researcher/experimenter")
    argParser.add_argument("-institution", "--institution", help="Name of institution")
    argParser.add_argument("-debug", "--debug", help="Display debug information", default=False)
    args = argParser.parse_args()
    return args


def displayParam(args):
    print("*"*40)
    print("USING THE FOLLOWING PARAMETERS:\n")
    print(f'INPUT FILE: {args.input_file} [ABSOLUTE PATH OR PATH RELATIVE TO CURRENT DIRECTORY]\n')

    global output_path #MODIFY GLOBAL VARIABLE FROM WITHIN FUNCTION
    if not args.output_path:
        print(f'OUTPUT FOLDER: {output_path} [DEFAULT: CURRENT WORKING DIRECTORY]\n')
    else:
        print(f'OUTPUT FOLDER: {args.output_path} [PASSED ARGUMENT]\n')
        output_path = args.output_path

    global experiment_modality
    experiment_modality_text = 'extracellular electrophysiology'
    if args.experiment_modality:#ONLY CHANGE FROM DEFAULT IF ARGUMENT PASSED IN
        if args.experiment_modality == "1":
            experiment_modality_text = 'extracellular electrophysiology'
        elif args.experiment_modality == "2":
            experiment_modality_text = 'Widefield Imaging'
        elif args.experiment_modality == "3":
            experiment_modality_text = '2Photon Imaging'
        elif args.experiment_modality == "4":
            experiment_modality_text = 'Behavioral'
        else:
            experiment_modality_text = 'fMRI'
        experiment_modality = args.experiment_modality
    print(f'EXPERIMENT MODALITY: {experiment_modality_text}\n')

    global researcher_experimenter
    if args.researcher_experimenter:
        researcher_experimenter = args.researcher_experimenter
        print(f'RESEARCHER/EXPERIMENTER (TERMINAL ARGUMENT): {researcher_experimenter}\n')

    global institution
    if args.institution:
        institution = args.institution
        print(f'INSTITUTION (TERMINAL ARGUMENT): {institution}\n')

    print("*" * 40)
    return args.input_file


def load_data(input_file, experiment_modality):
    '''Used for meta-data loading'''

    #DEFINE COMMONG FIELDS AMONG ALL DATASETS (EXCEL COLUMN HEADERS)
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

    #FIELD LIST RELATIVE TO EXPERIMENT MODALITY
    if experiment_modality == "1": #ephys
        exp_modality_specific_fields = [
            'stimulus_notes_include',
            'stimulus_notes_paradigm',
            'stimulus_notes_direct_electrical_stimulation',
            'stimulus_notes_direct_electrical_stimulation_paradigm',
            'pharmacology_notes_anesthetized_during_recording',
            'pharmacology',
            'electrode_device_name',
            'electrode_recordings',
            'electrode_recordings_type',
            'electrode_recordings_contact_material',
            'electrode_recordings_substrate',
            'electrode_recordings_system',
            'electrode_recordings_location',
            'electrode_filtering',
            'identifier']
    elif experiment_modality == "2":#widefield
        print("WARNING: experiment modality not complete")
        exp_modality_specific_fields = []
    elif experiment_modality == "3":#2photon
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
    elif experiment_modality == "4":#behavior
        exp_modality_specific_fields = [
            'session_start_time',
            'sensor_description',
            'ch3_in_36data',
            'ch4_in_36data',
            'ch5_in_36data',
            'ch6_in_36data',
            'device_name',
            'device_description',
            'device_manufacturer',
            'LCmat_sampling_rate',
            'LCmat_channel_description',
            'supplemental_annotation',
            'video_sampling_rate',
            'processing_file',
            'analysis_file',
            'notes_file',
            'stimulus_notes_file'
        ]
    elif experiment_modality == "5":#mri
        exp_modality_specific_fields = []
    else:
        #NOT DEFINED [YET]
        exp_modality_specific_fields = []
        


    #APPEND EXPERIMENT MODALITY SPECFIC FIELDS TO COMMON LIST
    lstNWBFields = commonFields + exp_modality_specific_fields
    
    matched_fields = []
    try:
        lstExtractionFields = pd.read_excel(input_file, sheet_name="auto", usecols=lstNWBFields,
                                            dtype={'stimulus_notes_file': str, 'notes_file': str}) #just extract columns/fields I need
        matched_fields = lstNWBFields
    except ValueError:
        # Read all columns, then force string conversion for critical fields
        lstExtractionFields = pd.read_excel(input_file, sheet_name="auto")
        fields_in_file = lstExtractionFields.columns.tolist()
        matched_fields = list(set(fields_in_file).intersection(lstNWBFields))
        
        # Ensure critical columns are strings even if not in lstNWBFields
        for col in ['stimulus_notes_file', 'notes_file']:
            if col in lstExtractionFields.columns:
                lstExtractionFields[col] = lstExtractionFields[col].astype(str)

        print(f"IMPORT WARNING [SOME FIELDS NOT MATCHED] - NWB FIELD COUNT {len(lstNWBFields)}; IMPORT SHEET FIELD COUNT {len(fields_in_file)}")
    finally:
        print(f"SCRIPT WILL CONTINUE WITH THE FOLLOWING FIELDS: {matched_fields}")
        print("*" * 40)

    # Filter rows where 'include_nwb' == 'y'
    if 'include_nwb' in lstExtractionFields.columns:
        lstExtractionFields = lstExtractionFields[
            lstExtractionFields['include_nwb'].astype(str).str.lower() == 'y'
        ]

    mask = (
        lstExtractionFields['stimulus_notes_file'].notna() &
        lstExtractionFields['stimulus_notes_file'].str.strip().ne('') &
        lstExtractionFields['notes_file'].notna() &
        lstExtractionFields['notes_file'].str.strip().ne('')
    )
    lstExtractionFields = lstExtractionFields[mask]

    return lstExtractionFields


def get_subject(age, subject_description, genotype, sex, species, subject_id, subject_weight, date_of_birth, subject_strain):
    '''Used for meta-data '''

    subject_age = 'P0D'  # DEFAULT VALUE
    if isinstance(age, int) == True:
        subject_age = "P" + str(int(age)) + "D"  # ISO 8601 Duration format - assumes 'days'
    elif isinstance(age, str) == True and re.search("^P*D$", age):  # STARTS WITH 'P' AND ENDS WITH 'D' (CORRECT FORMATTING)
        subject_age = age
        
    if date_of_birth is not None:
        dob = date_of_birth.to_pydatetime()  #convert pandas timestamp to python datetime format

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
                                 weight=str(subject_weight),
                                 date_of_birth=date_of_birth,
                                 strain=subject_strain
                            )
    return subject


def get_electrode_mapping_data(src_folder_directory, electrode_recordings_file, electrode_device_name, electrode_recordings_type, electrode_recordings_contact_material, electrode_recordings_substrate, electrode_recordings_system, electrode_recordings_location):
    '''Used for electrode measurements table processing (ephys)'''
    rhd_file = str(PurePath(src_folder_directory).stem) + '.rhd'
    base_directory = PurePath(src_folder_directory).parts[:-1] #remove last part of path
    input_filename = Path(output_path, *base_directory, electrode_recordings_file)
    print(f'\tREAD ELECTRODE MAPPINGS: {input_filename}')
    input_map = pd.read_excel(input_filename)

    #PROCESSING FOR ELECTRODE MAPPINGS V1 (LIST OF TUPLES PER ROW); DEFAULT, AND ASSOCIATED .rhd FILE
    electrode_mappings = input_map.loc[input_map['epFile'] == rhd_file]['mapping']

    #SEE JUPYTER NOTEBOOK (ephys_process.ipynb) IN ROOT FOLDER FOR ALTERNATIVE PROCESSING

    return electrode_mappings


def main():
    #################################################################
    # APP CONSTANTS (DEFAULT)
    researcher_experimenter = ""
    institution = ""
    experiment_modality = "1" #ephys
    #################################################################
    

    if len(sys.argv) > 1:
        args = collectArguments()
        print("USING CLI ARGUMENTS")
        print(f'ARGUMENTS COLLECTED: {args}')
        experiment_modality = args.experiment_modality
    else:
        print("MISSING ARGUMENTS; USING DEFAULTS")
        print(f'\'python {os.path.basename(__file__)} -h\' FOR HELP\n')
        args.output_path = output_path
        experiment_modality = experiment_modality
        args.researcher_experimenter = researcher_experimenter
        args.institution = institution
        args.debug = debug
    
    lstRecords = load_data(args.input_file, experiment_modality)
    
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
        
        #IF NO TIMEZONE INFO, USE LOCAL TIMEZONE
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
        if sex == 'Male' or sex == 'M':
            sex = 'M'
        elif sex == 'Female' or sex == 'F':
            sex = 'F'
        else:
            sex = 'U'  # unknown
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

        if researcher_experimenter == '': #from terminal line (takes priority)
            researcher_experimenter = row.experimenters
        
        if institution == '':#from terminal line (takes priority)
            institution = row.institution

            keywords = ['Researchers: ' + str(researcher_experimenter)]

        ##################################################################################
        # CONVERT .MAT FILES TO .h5
        ##################################################################################
        output_filename = None
        output_filename = str(session_id).replace('/', '_').replace('\\', '_') + '.nwb' # REPLACE SLASHES IN FILENAME WITH UNDERSCORE
        
        print(f'\tNWB OUTPUT FILENAME: {output_filename}')
        Path(output_path).mkdir(parents=True, exist_ok=True)

        input_path = row.recordings_folder_directory
        if row.analysis_file:
            #INDIVIDUAL FILE INGESTION (EXPLICITY DEFINED)
            input_files = [Path(input_path, str(row.analysis_file))]
        else:
            #SCAN ENTIRE DIRECTORY FOR .mat FILES
            input_files = list(Path(input_path).glob('*.mat')) # JUST MATLAB FOR NOW

        #EVEN ON SCRATCH, CREATE FOLDER STRUCTURE BASED ON INPUT PATH
        Path(scratch_path, str(Path(input_path).parent.name)).mkdir(parents=True, exist_ok=True)
        revised_scratch_path = Path(scratch_path, str(Path(input_path).parent.name))
        Path(args.output_path, str(Path(input_path).parent.name)).mkdir(parents=True, exist_ok=True)
        dest_path = Path(args.output_path, str(Path(input_path).parent.name), output_filename)
        
        if len(input_files) > 0:
            for file in input_files:
                filename = file.name
                print(f'\tCONVERTING FILE: {filename}')
                input_filename = Path(input_path, filename)
                
                data_io = utils.convert(input_filename, revised_scratch_path)
                     
        else:
            print(f'\tNO INPUT FILES FOUND IN: {input_path}')
            continue
        

        # base_input_path = os.path.dirname(input_path)
        

        # print(f'\tINPUT PATH: {input_path}, BASE INPUT PATH: {base_input_path}')
        # last_folder_in_path = os.path.basename(os.path.normpath(base_input_path))
        
        # if last_folder_in_path == dataset['src_folder_directory']:
        #     #ASSUMED DUPLICATE FOLDERS AT END OF PATH
        #     input_filename = Path(base_input_path, filename)
        # else:
        #     input_filename = Path(base_input_path, dataset['src_folder_directory'], filename)

        # print(f'\tINPUT FILE: {input_filename}')
        # print(f'\tOUTPUT FILE: {dest_path}')
        
        ##################################################################################
        # PROCESS META-DATA, GENERAL
        session_description = row.session_description
        surgery = None  # DEFAULT VALUE FOR SURGERY
        pharmacology = None  # DEFAULT VALUE FOR PHARMACOLOGY
        manual_start_time = None # DEFAULT VALUE FOR MANUAL START TIME
        exp_identifier = 'NA'
        # CONCATENATE STIMULUS NOTES (DEPENDS ON EXPERIMENT MODALITY)
        stimulus_notes = 'NA'
        pharmacology = 'NA'
        notes = 'NA'
        if experiment_modality == "4":
            stimulus_notes_file = row.stimulus_notes_file
            if pd.notna(stimulus_notes_file) and str(stimulus_notes_file).strip().lower() != 'nan' and len(str(stimulus_notes_file).strip()) > 0:
                path_stub = input_filename.parts[:-1]
                data_filename = Path(*path_stub, str(stimulus_notes_file))
                stimulus_notes = behavior.add_str_data(data_filename, 'stimulus_notes')
                print(f'\tINCLUDING DATA FROM FILE: {stimulus_notes_file}')

            notes_file = row.notes_file
            if pd.notna(notes_file) and str(notes_file).strip().lower() != 'nan' and len(str(notes_file).strip()) > 0:
                notes_file = row.notes_file
                path_stub = input_filename.parts[:-1]
                data_filename = Path(*path_stub, notes_file)
                notes = behavior.add_str_data(data_filename, 'notes')
                print(f'\tINCLUDING DATA FROM FILE: {notes_file}')
        else:
            if row.stimulus_notes_include == 1:  # 1 (include) or 0 (do not include)
                stimulus_notes = "Stimulus paradigm: " + str(row.stimulus_notes_paradigm) + "; "
                if row.stimulus_notes_direct_electrical_stimulation == 1:
                    stimulus_notes += "Direct electrical stimulation paradigm: " + str(
                        row.stimulus_notes_direct_electrical_stimulation_paradigm) + "; "

            if row.pharmacology_notes_anesthetized_during_recording == 1: # 1 (include) or 0 (do not include)
                pharmacology = row.pharmacology

        #TODO - ADD surgery (concatenated) if exists in dataframe

        ##################################################################################
        #CREATE NWB FILE (BASIC META-DATA)
        nwbfile = pynwb.NWBFile(session_description = session_description,
                                identifier = exp_identifier,
                                session_start_time = session_start_time,
                                experiment_description = experiment_description,
                                keywords = keywords,
                                surgery=surgery,
                                pharmacology=pharmacology,
                                stimulus_notes=stimulus_notes,
                                experimenter = researcher_experimenter,
                                institution = institution,
                                subject=subject,
                                notes=notes
                                )

        ##################################################################################
        # PROCESS META-DATA, ACCORDING TO EXPERIMENT MODALITY

        if experiment_modality == "1":
            ##################################################################################
            # CREATE/CONVERT ELECTRODES TABLE(S) OBJECT
            electrode_recordings_file = row.electrode_recordings
            electrode_mappings = get_electrode_mapping_data(input_filename,
                                electrode_recordings_file,
                                row.electrode_device_name,
                                row.electrode_recordings_type,
                                row.electrode_recordings_contact_material,
                                row.electrode_recordings_substrate,
                                row.electrode_recordings_system,
                                row.electrode_recordings_location).tolist()[0]

            #ref: https://stackoverflow.com/questions/51051136/extracting-content-between-curly-braces-in-python
            grouped_electrode_mappings = re.findall(r'\{(.*?)\}', electrode_mappings)
            electrode_mappings = [(counter, item) for counter, item in enumerate(grouped_electrode_mappings)]

            print(f'mappings: {type(grouped_electrode_mappings), len(grouped_electrode_mappings), grouped_electrode_mappings}')

            electrode_recordings_description = 'Type: ' + str(
                row.electrode_recordings_type) + '; Contact material: ' + str(
                row.electrode_recordings_contact_material) + '; Substrate: ' + str(
                row.electrode_recordings_substrate)

            electrode_headers = {'electrode_device_name': row.electrode_device_name,
                                    'electrode_recordings_description': electrode_recordings_description,
                                    'electrode_recordings_system': row.electrode_recordings_system,
                                    'electrode_recordings_location': row.electrode_recordings_location,
                                    'electrode_filtering': row.electrode_filtering}

            ##################################################################################
            if os.path.isfile(dest_path) != True:  # file conversion completed
                print(f'\tCONVERTING INTAN (.rhd) FILE TO NWB: {dest_path}')
                convert_to_nwb(intan_filename=str(input_filename),
                                nwb_filename=str(dest_path),
                                session_description=session_description,
                                blocks_per_chunk=1000,
                                use_compression=True,
                                compression_level=4,
                                lowpass_description='Unknown lowpass filtering process',
                                highpass_description='Unknown lowpass filtering process',
                                merge_files=False,
                                subject=subject,
                                surgery=surgery,
                                stimulus_notes=stimulus_notes,
                                pharmacology=pharmacology,
                                manual_start_time=manual_start_time,
                                exp_identifier=str(exp_identifier),
                                electrode_mappings=electrode_mappings,
                                experimenter=researcher_experimenter,
                                institution=institution,
                                electrode_headers=electrode_headers)
            else:
                print(f'\tINTAN (.rhd) FILE CONVERSION COMPLETE')

        elif experiment_modality == "4":
            if row.institution == 'Boston University':
                print("ECONOMO LAB DATA PROCESSING")
                print(f'\tRESULT NWB FILE WILL BE SAVED TO: {dest_path}')
                
            else:

                ##################################################################################
                # CREATE IMAGE SERIES OBJECT TO STORE VIDEO DATA
                video_sampling_rate = row.video_sampling_rate
                last_folder_in_path = os.path.basename(os.path.normpath(input_filename))
                path_stub = input_filename.parts[:-1]
                glob_pattern = last_folder_in_path + '_*.avi'
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))

                video_file_path = '' #.avi
                for video_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING/REFERENCING VIDEO FILE: {video_file_path}')
                relative_path_video_file = behavior.get_video_reference_data(video_file_path, dest_path)

                video_location_file_path = '' #.csv
                glob_pattern = session_id + '_*_*_torso.csv'
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))
                for video_location_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING/REFERENCING VIDEO LOCATION FILE: {video_location_file_path}')
                if video_location_file_path == '':
                    relative_path_video_location_file = video_location_file_path
                else:
                    relative_path_video_location_file = behavior.get_video_reference_data(video_location_file_path, dest_path)

                glob_pattern = session_id + '_*_ellipse_*.mat'
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))
                for comments_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING COMMENTS [RE: VIDEO FILE] FROM FILE: {comments_file_path}')
                img_comments = behavior.extract_img_series_data(comments_file_path)

                device = nwbfile.create_device(
                    name=row.device_name,
                    description=row.device_description,
                    manufacturer=row.device_manufacturer
                )

                ##################################################################################
                # https://pynwb.readthedocs.io/en/stable/tutorials/domain/images.html
                # Note: This approach references the video files and does not include them in nwb file
                behavior_external_file = ImageSeries(
                    name="ImageSeries",
                    external_file=[relative_path_video_file, relative_path_video_location_file],
                    description=session_description,
                    format="external",
                    rate=float(video_sampling_rate),
                    comments=img_comments
                )
                nwbfile.add_acquisition(behavior_external_file)
                ################################################################################

                ##################################################################################
                # ADD SENSOR DATA AS NDARRAY (TIME SERIES)
                time_series_name = 'raw_sensor_data'
                sensor_description = row.sensor_description

                video_sampling_rate_Hz = 100.0 #float

                glob_pattern = session_id + '_*_excel.xlsx' # .xlsx
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))
                for sensor_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING {time_series_name} DATA FROM FILE: {sensor_file_path}')

                # CREATE NWB BEHAVIOR MODEL [TO WHICH WE WILL ADD TIME SERIES, GEOMETRY, ETC.]
                behavioral_time_series = behavior.add_timeseries_data(sensor_file_path, video_sampling_rate_Hz, time_series_name, sensor_description)

                behavior_module = nwbfile.create_processing_module(
                    name=time_series_name, description=sensor_description
                )
                behavior_module.add(behavioral_time_series)
                ##################################################################################

                ##################################################################################
                # ADD DATA [36DATA] AS NDARRAY (TIME SERIES)
                ##################################################################################
                time_series_name = 'data_36columns'
                time_series_description = str(row.ch3_in_36data) + '|' + str(row.ch4_in_36data) + '|' + str(row.ch5_in_36data) + '|' + str(row.ch6_in_36data)
                video_sampling_rate_Hz = 2000.0  # sampling rate in Hz

                glob_pattern = session_id + '_*_36data.mat' # .mat
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))
                for time_series_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING {time_series_name} DATA FROM FILE: {time_series_file_path}')

                behavioral_time_series = behavior.add_timeseries_data(time_series_file_path, video_sampling_rate_Hz,
                                                                        time_series_name, time_series_description)

                behavior_module = nwbfile.create_processing_module(
                    name=time_series_name, description=time_series_description
                )
                behavior_module.add(behavioral_time_series)
                ##################################################################################

                ##################################################################################
                # ADD OTHER META-DATA [LCmat] AS NDARRAY (TIME SERIES)
                ##################################################################################
                time_series_name = 'raw_labchart_data'
                time_series_description =row.LCmat_channel_description
                video_sampling_rate_Hz = float(row.LCmat_sampling_rate) # sampling rate in Hz

                glob_pattern = session_id + '_*_LCmat.mat'  # .mat
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))
                for other_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING {time_series_name} LOG DATA FROM FILE: {other_file_path}')

                behavioral_time_series = behavior.add_timeseries_data(other_file_path, video_sampling_rate_Hz,
                                                                        time_series_name, time_series_description)

                behavior_module = nwbfile.create_processing_module(
                    name=time_series_name, description=time_series_description
                )
                behavior_module.add(behavioral_time_series)

                ##################################################################################
                # ADD PROCESSING DATA REF AS TUPLE
                ##################################################################################
                processing_file = row.processing_file
                name = 'signal_percentiles'
                description = 'Percentiles of the 36-data signals.'

                if processing_file:
                    data_filename = Path(*path_stub, processing_file)
                    processing_data = behavior.add_matrix_data(data_filename, 'processing', description)

                    behavior_module = nwbfile.create_processing_module(
                        name=name, description=description
                    )

                    behavior_module.add(processing_data)

                    print(f'\tINCLUDING {processing_file} DATA FROM FILE: {data_filename}')

                ##################################################################################
                # ADD ANALYSIS DATA REF AS TUPLE
                ##################################################################################
                analysis_file = row.analysis_file
                name = 'behavioral_booleans'
                description = 'Annotated masks for pre-defined behaviors (usable, head-torso, both)'

                if analysis_file:
                    data_filename = Path(*path_stub, analysis_file)
                    analysis_data = behavior.add_matrix_data(data_filename, 'analysis', description)

                    behavior_module = nwbfile.create_processing_module(
                        name=name, description=description
                    )
                    behavior_module.add(analysis_data)

                    print(f'\tINCLUDING {analysis_file} DATA FROM FILE: {data_filename}')


            # WRITE NWB FILE TO STORAGE
            print(f'\tWRITING NWB FILE TO STORAGE: {dest_path}')
            with pynwb.NWBHDF5IO(dest_path, 'w') as io:
                io.write(nwbfile)

        else:
            print("not complete")


        #
        #     #check if optical_channel1 is used
        #     if str(dataset["optical_channel_name"]) != 'nan':
        #         optical_channel = OpticalChannel(
        #             name = dataset['optical_channel_name'],
        #             description = dataset['optical_channel_description'],
        #             emission_lambda = float(dataset['optical_channel_emission_lambda'])
        #         )
        #         imaging_plane = nwbfile.create_imaging_plane(
        #             name = dataset['image_stack_name'],
        #             description=dataset['image_stack_description'],
        #             device = device,
        #             optical_channel = optical_channel,
        #             imaging_rate = float(dataset['image_stack_imaging_rate']),
        #             excitation_lambda = float(dataset['image_stack_exitation_lambda']),
        #             indicator = dataset['image_stack_indicator'],
        #             location = dataset['image_stack_location'],
        #             grid_spacing = literal_eval(dataset['image_stack_grid_spacing']),
        #             grid_spacing_unit = dataset['image_stack_grid_spacing_unit']
        #         )
        #
        #     ##################################################################################
        #     #ADD FILE DATA (IMAGE STACK)
        #
        #
        #
        #     data = tifffile.imread(input_filename)
        #     rate = float(dataset['image_stack_imaging_rate'])
        #
        #     image_series = TwoPhotonSeries(
        #         name='TwoPhotonSeries',
        #         data = data,
        #         imaging_plane=imaging_plane,
        #         rate=rate,
        #         unit='NA',
        #     )
        #
        #     nwbfile.add_acquisition(image_series)
        #
        #     ##################################################################################
        #     #WRITE NWB FILE TO STORAGE
        #     with pynwb.NWBHDF5IO(dest_path, 'w') as io:
        #         io.write(nwbfile)
        #
        #     ##################################################################################

            #VALIDATE .NWB FILE (FOR COMPLIANCE WITH CURRENT SPEC)
        #    print(f'VALIDATING OUTPUT FILE: {dest_path}')
            #exec(open(f'nwbinspector {dest_path}').read())
            #nwbinspector .. /../ output / run03_airpuff_hindlimb_40psi_200924_155523.nwb - -config
            #dandi


    else:
        print("MISSING ARGUMENTS; UNABLE TO CONTINUE")
        print(f'\'python {os.path.basename(__file__)} -h\' FOR HELP\n')
        exit()


if __name__ == "__main__":
    main()