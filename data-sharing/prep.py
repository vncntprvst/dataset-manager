# CREATED: 11-APR-2023
# LAST EDIT: 4-MAY-2023
# AUTHOR: DUANE RINEHART, MBA (drinehart@ucsd.edu)

'''TERMINAL CONVERSION SCRIPT FOR MULTIPLE EXPERIMENTAL MODALITIES'''

import os, sys, pynwb, re, glob
from pathlib import Path, PurePath
import argparse
import pandas as pd
from datetime import datetime
from dateutil.tz import tzlocal
from scipy.io import loadmat

from pynwb import NWBHDF5IO, NWBFile
from pynwb.image import ImageSeries

parent = Path(__file__).parents[1] #2 levels up
sys.path.append(parent)
print(f'USING PARENT PATH REFERENCES FOR IMPORTS: {parent}')

sys.path.insert(1, 'lib')
sys.path.insert(1, 'converters')

import utils
import behavior
from ConvertIntanToNWB import convert_to_nwb

#################################################################
# APP CONSTANTS (DEFAULT)
output_path = Path(os.getcwd(), 'output')
experiment_modality = 1 #ephys
experiment_description = None #string or null
researcher_experimenter = ""
institution = ""
# debug = True
#################################################################

def displayMenu():
    print('DATA SHARING COMMAND LINE INTERFACE\n')
    print('SEE REPOSITORY (https://github.com/ActiveBrainAtlas2/nwb) OR EVALUATE CODE FOR ARGUMENTS\n')


def collectArguments():
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-i", "--input_file", help="Input file (.xlsx) containing experimental parameters/data locations")
    argParser.add_argument("-o", "--output_path",
                           help="Output folder/path where converted nwb files will be stored")
    argParser.add_argument("-exp", "--experiment_modality",
                           help="Valid experiment modes: 1=ephys, 2=widefield, 3=2Photon, 4=fMRI")
    argParser.add_argument("-researcher", "--researcher_experimenter",
                           help="Name(s) of researcher/experimenter")
    argParser.add_argument("-institution", "--institution",
                           help="Name of institution")
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
    elif experiment_modality == "5":#calcium imaging
        print("WARNING: experiment modality not complete")
        exp_modality_specific_fields = []


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


def get_subject(age, subject_description, genotype, sex, species, subject_id, subject_weight, date_of_birth, subject_strain):
    '''Used for meta-data '''
    subject_age = "P0D"  # generic default
    if isinstance(age, str) != True:
        try:
            subject_age = "P" + str(int(age)) + "D" #ISO 8601 Duration format - assumes 'days'
        except:
            pass

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
    displayMenu()
    if len(sys.argv) > 1:
        args = collectArguments()
        input_path = displayParam(args)

        lstRecords = load_data(args.input_file, experiment_modality).to_dict('records')  # creates list of dictionaries

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
            global researcher_experimenter
            if researcher_experimenter == '':#from terminal line (takes priority)
                researcher_experimenter = dataset['experimenters']
            global institution
            if institution == '':#from terminal line (takes priority)
                institution = dataset['institution']
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
            base_input_path = os.path.dirname(input_path)
            last_folder_in_path = os.path.basename(os.path.normpath(base_input_path))

            if last_folder_in_path == dataset['src_folder_directory']:
                #ASSUMED DUPLICATE FOLDERS AT END OF PATH
                input_filename = Path(base_input_path, filename)
            else:
                input_filename = Path(base_input_path, dataset['src_folder_directory'], filename)

            print(f'\tINPUT FILE: {input_filename}')
            print(f'\tOUTPUT FILE: {dest_path}')
            keywords = ['Researchers: ' + str(researcher_experimenter)]

            ##################################################################################
            # PROCESS META-DATA, GENERAL
            session_description = dataset['session_description']
            surgery = None  # DEFAULT VALUE FOR SURGERY
            pharmacology = None  # DEFAULT VALUE FOR PHARMACOLOGY
            manual_start_time = None # DEFAULT VALUE FOR MANUAL START TIME
            exp_identifier = dataset['identifier']
            session_start_time = datetime(2023, 3, 2, tzinfo=tzlocal())#use current day

            # CONCATENATE STIMULUS NOTES (DEPENDS ON EXPERIMENT MODALITY)
            stimulus_notes = 'NA'
            pharmacology = 'NA'
            notes = 'NA'
            if experiment_modality == "4":
                stimulus_notes_file = dataset['stimulus_notes_file']
                path_stub = input_filename.parts[:-1]
                data_filename = Path(*path_stub, stimulus_notes_file)
                stimulus_notes = behavior.add_str_data(data_filename, 'stimulus_notes')
                print(f'\tINCLUDING DATA FROM FILE: {stimulus_notes_file}')

                notes_file = dataset['notes_file']
                path_stub = input_filename.parts[:-1]
                data_filename = Path(*path_stub, notes_file)
                notes = behavior.add_str_data(data_filename, 'notes')
                print(f'\tINCLUDING DATA FROM FILE: {notes_file}')
            else:
                if dataset['stimulus_notes_include'] == 1:  # 1 (include) or 0 (do not include)
                    stimulus_notes = "Stimulus paradigm: " + str(dataset['stimulus_notes_paradigm']) + "; "
                    if dataset['stimulus_notes_direct_electrical_stimulation'] == 1:
                        stimulus_notes += "Direct electrical stimulation paradigm: " + str(
                            dataset['stimulus_notes_direct_electrical_stimulation_paradigm']) + "; "

                if dataset['pharmacology_notes_anesthetized_during_recording'] == 1: # 1 (include) or 0 (do not include)
                    pharmacology = dataset['pharmacology']

            if dataset['session_start_time']:
                session_start_time = dataset['session_start_time'].to_pydatetime().replace(tzinfo=tzlocal()) #replace non-existent (presumed) timezone with local timezone

            #TODO - ADD surgery (concatenated) if exists in dataframe


            ##################################################################################
            #CREATE NWB FILE (BASIC META-DATA)
            nwbfile = pynwb.NWBFile(session_description = dataset['session_description'],
                                    identifier = str(exp_identifier),
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
                electrode_recordings_file = dataset['electrode_recordings']
                electrode_mappings = get_electrode_mapping_data(input_filename,
                                    electrode_recordings_file,
                                    dataset['electrode_device_name'],
                                    dataset['electrode_recordings_type'],
                                    dataset['electrode_recordings_contact_material'],
                                    dataset['electrode_recordings_substrate'],
                                    dataset['electrode_recordings_system'],
                                    dataset['electrode_recordings_location']).tolist()[0]

                #ref: https://stackoverflow.com/questions/51051136/extracting-content-between-curly-braces-in-python
                grouped_electrode_mappings = re.findall(r'\{(.*?)\}', electrode_mappings)
                electrode_mappings = [(counter, item) for counter, item in enumerate(grouped_electrode_mappings)]

                print(f'mappings: {type(grouped_electrode_mappings), len(grouped_electrode_mappings), grouped_electrode_mappings}')

                electrode_recordings_description = 'Type: ' + str(
                    dataset['electrode_recordings_type']) + '; Contact material: ' + str(
                    dataset['electrode_recordings_contact_material']) + '; Substrate: ' + str(
                    dataset['electrode_recordings_substrate'])

                electrode_headers = {'electrode_device_name': dataset['electrode_device_name'],
                                     'electrode_recordings_description': electrode_recordings_description,
                                     'electrode_recordings_system': dataset['electrode_recordings_system'],
                                     'electrode_recordings_location': dataset['electrode_recordings_location'],
                                     'electrode_filtering': dataset['electrode_filtering']}

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
                ##################################################################################
                # CREATE IMAGE SERIES OBJECT TO STORE VIDEO DATA
                video_sampling_rate = dataset['video_sampling_rate']
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
                relative_path_video_location_file = behavior.get_video_reference_data(video_location_file_path, dest_path)

                glob_pattern = session_id + '_*_ellipse_*.mat'
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))
                for comments_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING COMMENTS [RE: VIDEO FILE] FROM FILE: {comments_file_path}')
                img_comments = behavior.extract_img_series_data(comments_file_path)

                device = nwbfile.create_device(
                    name=dataset['device_name'],
                    description=dataset['device_description'],
                    manufacturer=dataset['device_manufacturer']
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
                sensor_description = dataset['sensor_description']

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
                time_series_description = str(dataset['ch3_in_36data']) + '|' + str(dataset['ch4_in_36data']) + '|' + str(dataset['ch5_in_36data']) + '|' + str(dataset['ch6_in_36data'])
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
                time_series_description = dataset['LCmat_channel_description']
                video_sampling_rate_Hz = float(dataset['LCmat_sampling_rate']) # sampling rate in Hz

                glob_pattern = session_id + '_*_LCmat.mat'  # .mat
                base_path_with_pattern = str(Path(*path_stub, glob_pattern))
                for other_file_path in glob.glob(base_path_with_pattern, recursive=False):
                    print(f'\tINCLUDING {time_series_name} LOG DATA FROM FILE: {other_file_path}')

                behavioral_time_series = behavior.add_timeseries_data(time_series_file_path, video_sampling_rate_Hz,
                                                                      time_series_name, time_series_description)

                behavior_module = nwbfile.create_processing_module(
                    name=time_series_name, description=time_series_description
                )
                behavior_module.add(behavioral_time_series)

                ##################################################################################
                # ADD PROCESSING DATA REF AS TUPLE
                ##################################################################################
                processing_file = dataset['processing_file']

                if processing_file:
                    data_filename = Path(*path_stub, processing_file)
                    processing_data = behavior.add_tuple_data(data_filename, 'processing')

                    processing_data = []
                    processing_data_module = nwbfile.create_processing_module(
                        name='signal_percentiles', description="Percentiles of the 36-data signals."
                    )
                    processing_data_module.add(processing_data)
                    print(f'\tINCLUDING {processing_file} DATA FROM FILE: {data_filename}')

                ##################################################################################
                # ADD ANALYSIS DATA REF AS TUPLE
                ##################################################################################
                analysis_file = dataset['analysis_file']

                if analysis_file:
                    data_filename = Path(*path_stub, analysis_file)
                    analysis_data = behavior.add_tuple_data(data_filename, 'analysis')

                    analysis_data = []
                    processing_data_module = nwbfile.create_processing_module(
                        name='behavioral_booleans', description="Annotated masks for pre-defined behaviors (usable, head-torso, both)"
                    )
                    processing_data_module.add(analysis_data)
                    print(f'\tINCLUDING {analysis_file} DATA FROM FILE: {data_filename}')

                # WRITE NWB FILE TO STORAGE
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