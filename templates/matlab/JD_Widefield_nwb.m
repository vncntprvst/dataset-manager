%JD_Widefield_nwb.m

%%
%#################################################################
% APP CONSTANTS (DEFAULT)
clear; clc; close all;
primary_experiments_table = readtable('\\birdstore.dk.ucsd.edu\data\Jacob\nwb_process\JD_input_widefield.xlsx'); %EXPERIMENTAL SUBJECT: PRIMARY DATA INGESTION TABLE
output_path = "C:\tmp\output_7_31_24_Test\"; %NWB file written to this location
% summary_data_path = "Z:\drinehart\VesCorrPhase\"; %formerly 'input_path'
summary_data_path = "Y:\DataAnalysis\VesCorrPhase"; %formerly 'input_path'
%#################################################################

%PRE-PROCESSING / PREREQUISITES
% Check if output_path exists, create it if not
if ~exist(output_path, 'dir')
    mkdir(output_path);
end
warning('off','all')

%#################################################################
%PROCESS EACH LINE (EXPERIMENTAL SUBJECT) OF primary_experiments_table
%#################################################################
for subj = 1:length(primary_experiments_table.age)
    for trial = 1:1 %Iterate over trials for current animal.
        %Load recordings table
        src_folder_directory = primary_experiments_table.src_folder_directory{subj};
        experiment_specific_table = readtable(src_folder_directory);

        %#################################################################
        %Populate subject specific information
        %#################################################################
        age = string(primary_experiments_table.age(subj));
        if startsWith(age,'P') && endsWith(age,'D')
            subj_age = age
        elseif startsWith(age,'P') && ~endsWith(age,'D')
            subj_age = strcat(age,'D')
        elseif ~startsWith(age,'P') && endsWith(age,'D')
            subj_age = strcat('P',age)
        elseif ~startsWith(age,'P') && ~endsWith(age,'D')
            subj_age = strcat('P',age,'D')
        end
        subj_species = primary_experiments_table.species(subj);
        subj_sex = primary_experiments_table.sex(subj);
        subj_id = primary_experiments_table.subject_id(subj);
        subj_description = primary_experiments_table.subject_description(subj);
        subj_strain = primary_experiments_table.subject_strain(subj);
        subj_DOB = primary_experiments_table.date_of_birth_YYYY_MM_DD_(subj);
        subj_genotype = primary_experiments_table.genotype(subj);
        subj_figs = primary_experiments_table.session_description(subj);
        subj_session_id = primary_experiments_table.session_id(subj);
        subj_surgery = primary_experiments_table.surgery(subj);


        %#################################################################
        %Populate experiment-specific information
        %#################################################################
        exp_stim = experiment_specific_table.stimulus_notes(trial);
        exp_device = experiment_specific_table.device_name(trial);
        exp_device_description = experiment_specific_table.device_description(trial);
        exp_imaging_plane_description = experiment_specific_table.imaging_plane_description(trial);
        exp_optical_channel_description = experiment_specific_table.optical_channel_description(trial);
        exp_imaging_plane_location = experiment_specific_table.imaging_plane_location(trial);
        exp_imaging_plane_exitation_lambda = experiment_specific_table.imaging_plane_exitation_lambda(trial);
        exp_optical_channel_emission_lambda = experiment_specific_table.optical_channel_emission_lambda(trial);
        exp_imaging_plane_imaging_rate = experiment_specific_table.imaging_plane_imaging_rate(trial);
        exp_imaging_plane_indicator = experiment_specific_table.imaging_plane_indicator(trial);
        
        %ADD META-DATA TO NWB OBJECT:
        tmp_Subject = getsubject(char(subj_age),'days',subj_species,subj_sex,subj_id,subj_description,subj_strain,subj_DOB,subj_genotype);
        researcher_experimenter = primary_experiments_table.experimenters(subj);
        institution = primary_experiments_table.institution(subj);

        nwb = NwbFile(...
            'session_description', 'Long-wavelength traveling waves of vasomotion modulate the perfusion of cortex', ...
            'identifier', subj_session_id, ...
            'session_start_time', datetime('today',TimeZone="America/Los_Angeles"), ...
            'general_experimenter', researcher_experimenter, ...
            'general_institution', institution, ...
            'general_experiment_description',exp_imaging_plane_description, ...
            'general_keywords','Neurovascular coupling, oscillator, penetrating arteriole, perfusion, pia, resting state, vasodynamics',...
            'surgery',subj_surgery,...
            'stimulus_notes',exp_stim...
            );
        nwb.general_subject = types.core.Subject();
        nwb.general_subject = tmp_Subject;

        % Add device object
        device1 = types.core.Device( ...
            'name', exp_device{1}, ...
            'description', exp_device_description{1});
        nwb.general_devices.set('Imaging device',device1);

        % Create ImagingPlane object. how much of this info is in meta data text file?
        % Read pixel information from tif header?
        optical_channel = types.core.OpticalChannel( ...
            'description', exp_optical_channel_description, ...
            'emission_lambda', exp_optical_channel_emission_lambda);
        imaging_plane_name = exp_imaging_plane_description;
        imaging_plane = types.core.ImagingPlane( ...
            'optical_channel', optical_channel, ...
            'device', device1, ...
            'excitation_lambda', exp_imaging_plane_exitation_lambda, ...
            'imaging_rate', exp_imaging_plane_imaging_rate, ...
            'indicator', exp_imaging_plane_indicator, ...
            'location', exp_imaging_plane_location);

        %#################################################################
        % PROCESS RAW IMAGES BELOW
        %#################################################################
        process_images(experiment_specific_table, imaging_plane, trial,nwb)
        
        %#################################################################
        % PROCESS SUMMARY FIGURES BELOW %
        %#################################################################
        GenTimeSeries(subj_figs,summary_data_path,nwb)
        GenDynamicTables(subj_figs,summary_data_path,nwb)

        %% Final export start
        nwbExport(nwb, fullfile(output_path, ['Subject_',sprintf('%.0f',subj),'_',strrep(subj_session_id{1},'-','_'),'.nwb']));
        clearvars nwb
    end
end

%% LOAD AND SAVE IMAGES 
function process_images(experiment_specific_table, imaging_plane, trial,nwb)
% READ src_folder_directory LOCATION (EXCEL FILE)
% LOOP THROUGH EXCEL FILENAMES
% READ IMAGE FILE
% STORE IN NWB FORMAT
disp(['READING LOCATION: ', experiment_specific_table.recordings_folder{trial}])
isstack = experiment_specific_table.isstack(trial);
if isstack == 1
    %Read image stack at location in recordings_folder
    im_loc = convertCharsToStrings(experiment_specific_table.recordings_folder{trial});
    im_loc_rep = strrep(im_loc," ","*");
    outvars = pyrunfile(sprintf("TiffDimDetector.py %s",im_loc_rep),'imlength'); 
    ims = str2double(outvars.char)
    img_data = pyrunfile(sprintf("TiffImReader.py %s",im_loc_rep),'imOutput', r1 = int16(0), r2 = int16(ims), r3 = int16(1));
    % img_data = shiftdim(uint16(img_data_tmp),1);
    img_data = int16(img_data);
elseif isstack == 0
    %Read images one-by-one
    im_loc = convertCharsToStrings(experiment_specific_table.recordings_folder{trial});
    cd(im_loc)
    ims_files = dir('*.tif');
    %How many images to read? first 500s UPDATE THIS
    T = round(500*experiment_specific_table.imaging_plane_imaging_rate(trial));
    im_cell = cell(T,1);
    for i = 1:T
        im_cell{i} = imread(ims_files(i).name);
        if mod(i,100) == 0
            disp(['Reading Image ',num2str(i),' of ',num2str(T)])
        end
    end
    img_data = cat(3, im_cell{:});
    clear im_cell
    img_data = permute(img_data,[3,1,2]);
else
    disp('ERROR: Image type not read')
end

if contains(experiment_specific_table.device_name{trial},'2-Photon','IgnoreCase',true)
%'data' first dimension needs to be time.
InternalImageSeries = types.core.TwoPhotonSeries( ...
    'imaging_plane', imaging_plane, ...
    'starting_time', 0.0, ...
    'starting_time_rate', experiment_specific_table.imaging_plane_imaging_rate(trial), ...
    'data', img_data);
elseif contains(experiment_specific_table.device_name{trial},'Wide-field','IgnoreCase',true)
InternalImageSeries = types.core.OnePhotonSeries( ...
    'imaging_plane', imaging_plane, ...
    'data', img_data);
else
    disp('WARNING NO ACQUISITION TYPE DETECTED')
end

nwb.acquisition.set('ImageSeries', InternalImageSeries);
end

%% Generate subject object
function [tmp_Subject] = getsubject(age,age_description,species,sex,subject_id,description,strain,DOB,genotype)
tmp_Subject = types.core.Subject( ...
    'age', age, ...
    'age_description',age_description, ...
    'species', species, ...
    'sex', sex, ...
    'subject_id', subject_id, ...
    'description', description,...
    'strain',strain,...
    'date_of_birth',datetime(DOB,TimeZone="America/Los_Angeles"),...
    'genotype',genotype...
    );
end

function GenTimeSeries(subj_figs,summary_data_path,nwb)
addpath('FigFunctions\')
Fig1D(subj_figs,summary_data_path,nwb);
FigS4B(subj_figs,summary_data_path,nwb);
end

function GenDynamicTables(subj_figs,summary_data_path,nwb)
addpath('FigFunctions\')
Fig1E(subj_figs,summary_data_path,nwb);
Fig1F(subj_figs,summary_data_path,nwb);
Fig1G(subj_figs,summary_data_path,nwb);
Fig1H(subj_figs,summary_data_path,nwb);
Fig1I(subj_figs,summary_data_path,nwb);
Fig1J(subj_figs,summary_data_path,nwb);
Fig2C(subj_figs,summary_data_path,nwb);
Fig2D(subj_figs,summary_data_path,nwb);
Fig2E(subj_figs,summary_data_path,nwb);
Fig2H(subj_figs,summary_data_path,nwb);
Fig2F(subj_figs,summary_data_path,nwb);
Fig3C(subj_figs,summary_data_path,nwb);
Fig3D(subj_figs,summary_data_path,nwb);
Fig4B(subj_figs,summary_data_path,nwb);
Fig4C(subj_figs,summary_data_path,nwb);
Fig4D(subj_figs,summary_data_path,nwb);
Fig4E(subj_figs,summary_data_path,nwb);
Fig4F(subj_figs,summary_data_path,nwb);
Fig5A(subj_figs,summary_data_path,nwb);
Fig5B(subj_figs,summary_data_path,nwb);
Fig5C(subj_figs,summary_data_path,nwb);
Fig6B(subj_figs,summary_data_path,nwb);
Fig6C(subj_figs,summary_data_path,nwb);
Fig6D(subj_figs,summary_data_path,nwb);
Fig6E(subj_figs,summary_data_path,nwb);
Fig6F(subj_figs,summary_data_path,nwb);
FigS2A(subj_figs,summary_data_path,nwb);
FigS2B(subj_figs,summary_data_path,nwb);
FigS2C(subj_figs,summary_data_path,nwb);
FigS2D(subj_figs,summary_data_path,nwb);
FigS2E(subj_figs,summary_data_path,nwb);
FigS2F(subj_figs,summary_data_path,nwb);
FigS2G(subj_figs,summary_data_path,nwb);
FigS2H(subj_figs,summary_data_path,nwb);
FigS3A(subj_figs,summary_data_path,nwb);
FigS3B(subj_figs,summary_data_path,nwb);
FigS3C(subj_figs,summary_data_path,nwb);
FigS3D(subj_figs,summary_data_path,nwb);
FigS3E(subj_figs,summary_data_path,nwb);
FigS3F(subj_figs,summary_data_path,nwb);
FigS4C(subj_figs,summary_data_path,nwb);
FigS4D(subj_figs,summary_data_path,nwb);
FigS5(subj_figs,summary_data_path,nwb);
FigS6A(subj_figs,summary_data_path,nwb);
FigS6B(subj_figs,summary_data_path,nwb);
FigS6C(subj_figs,summary_data_path,nwb);
FigS7A(subj_figs,summary_data_path,nwb);
FigS7B(subj_figs,summary_data_path,nwb);
FigS7C(subj_figs,summary_data_path,nwb);
FigS8A(subj_figs,summary_data_path,nwb);
FigS8B(subj_figs,summary_data_path,nwb);
FigS8C(subj_figs,summary_data_path,nwb);
end


%% Testing
% ds = datastore(current_folder,"FileExtensions",".tif",'Type', 'image');
% img_data = tall(ds); %Need to "gather" the tall array before saving to nwb. Try using "matfile" instead. OR Process on computer with larger memory.
% disp(['TIF files in folder: ' current_folder]);
% for i = 1:length(tif_files)
%     disp(tif_files(i).name);
% end
% disp(' ');

% Define a file path for temporary storage
% temp_file = 'temp_image_data.mat';
% Initialize matfile for writing
% matObj = matfile(temp_file, 'Writable', true);
% matObj.image_data = zeros(array_size, 'single'); % Adjust data type if needed