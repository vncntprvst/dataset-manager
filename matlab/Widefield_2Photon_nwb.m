%Widefield_2Photon_nwb.m

%REMOVE DETAIL, IF NOT RELEVANT FOR PROCESSING: (JACOB TO CLEAN UP)
%%Save data as csv in individual image folder. Get rid of plotting.
%Save separate nwb file for each subject. Associate data with figure

%Make figure saving functions
%Don't create figures poping up

%% Nice to have
%Add imaging_plane excitation lambda rate etc.
%drop in images from figures.
%%

%#################################################################
% APP CONSTANTS (DEFAULT)
clear; clc; close all;
primary_experiments_table = readtable('\\birdstore.dk.ucsd.edu\data\Jacob\nwb_process\input_widefield_2P.xlsx'); %EXPERIMENTAL SUBJECT: PRIMARY DATA INGESTION TABLE
output_path = "C:\tmp\output\"; %NWB file written to this location
summary_data_path = "Z:\drinehart\VesCorrPhase\"; %Duane test
% summary_data_path = "Y:\DataAnalysis\VesCorrPhase"; %Jacob test
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
    recordings_data_file = primary_experiments_table.src_folder_directory(subj);

    %Initialize subject information
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
    % Determine which experiment data to include with this subject.
    subj_figs = primary_experiments_table.session_description(subj);
    subj_session_id = primary_experiments_table.session_id(subj);
    subj_surgery = primary_experiments_table.surgery(subj);
    subj_stim = primary_experiments_table.stimulus_notes(subj);

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
        'general_experiment_description','Two-photon and Wide-field experiments on pial and penetrating arterioles', ...
        'general_keywords','Neurovascular coupling, oscillator, penetrating arteriole, perfusion, pia, resting state, vasodynamics',...
        'surgery',subj_surgery,...
        'stimulus_notes',subj_stim...
        );
    nwb.general_subject = types.core.Subject();
    nwb.general_subject = tmp_Subject;
    nwb;

    %% Add device object
    subj_device = primary_experiments_table.device_name(subj);
    subj_device_description = primary_experiments_table.device_description(subj);
    device1 = types.core.Device( ...
        'name', subj_device{1}, ...
        'description', subj_device_description{1});
    nwb.general_devices.set('Imaging device',device1);
   
    %#################################################################
    % PROCESS SUMMARY FIGURES BELOW %
    %#################################################################
    % GenTimeSeries(subj_figs, summary_data_path, nwb)
    % GenDynamicTables(subj_figs, summary_data_path, nwb)

    %#################################################################
    % PROCESS [IMAGE] RECORDINGS BELOW %
    %#################################################################
    ProcessImages(subj_id, recordings_data_file, nwb);

     %% Final export start
     nwbExport(nwb, fullfile(output_path, ['Subject_',sprintf('%.0f',subj),'_',strrep(subj_session_id{1},'-','_'),'.nwb']));
     clearvars nwb
end

%% #################################################################
% NWB: Generate subject object
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
%% #################################################################
function ProcessImages(subj_id, recordings_data_file, nwb)
    addpath('lib\')
    process_images(subj_id, recordings_data_file, nwb);
end
%% #################################################################
function GenTimeSeries(subj_figs, summary_data_path, nwb)
    addpath('FigFunctions\')
    Fig1D(subj_figs,summary_data_path,nwb);
    % FigS4B(subj_figs,summary_data_path,nwb);
end
%% #################################################################
function GenDynamicTables(subj_figs, summary_data_path, nwb)
    addpath('FigFunctions\')
    Fig1E(subj_figs,summary_data_path,nwb);
    Fig1F(subj_figs,summary_data_path,nwb);
    Fig1G(subj_figs,summary_data_path,nwb);
    Fig1H(subj_figs,summary_data_path,nwb);
    Fig1I(subj_figs,summary_data_path,nwb);
    Fig1J(subj_figs,summary_data_path,nwb);
    Fig2C(subj_figs,summary_data_path,nwb); %time series?
    Fig2D(subj_figs,summary_data_path,nwb);
    Fig2E(subj_figs,summary_data_path,nwb);
    Fig2H(subj_figs,summary_data_path,nwb);
    Fig2F(subj_figs,summary_data_path,nwb);
    % Fig3C(subj_figs,summary_data_path,nwb);
    Fig3D(subj_figs,summary_data_path,nwb);
    % Fig4B(subj_figs,summary_data_path,nwb);
    % Fig4C(subj_figs,summary_data_path,nwb);
    % Fig4D(subj_figs,summary_data_path,nwb);
    Fig4E(subj_figs,summary_data_path,nwb);
    Fig4F(subj_figs,summary_data_path,nwb);
    % Fig5A(subj_figs,summary_data_path,nwb);
    Fig5B(subj_figs,summary_data_path,nwb);
    % Fig5C(subj_figs,summary_data_path,nwb);
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
    % FigS2H(subj_figs,summary_data_path,nwb);
    FigS3A(subj_figs,summary_data_path,nwb);
    FigS3B(subj_figs,summary_data_path,nwb);
    FigS3C(subj_figs,summary_data_path,nwb);
    FigS3D(subj_figs,summary_data_path,nwb);
    FigS3E(subj_figs,summary_data_path,nwb);
    FigS3F(subj_figs,summary_data_path,nwb);
    % FigS4C(subj_figs,summary_data_path,nwb);
    % FigS4D(subj_figs,summary_data_path,nwb);
    FigS5(subj_figs,summary_data_path,nwb);
    FigS6A(subj_figs,summary_data_path,nwb);
    FigS6B(subj_figs,summary_data_path,nwb);
    FigS6C(subj_figs,summary_data_path,nwb);
    FigS7A(subj_figs,summary_data_path,nwb);
    FigS7B(subj_figs,summary_data_path,nwb);
    FigS7C(subj_figs,summary_data_path,nwb);
    % FigS8A(subj_figs,summary_data_path,nwb);
    % FigS8B(subj_figs,summary_data_path,nwb);
    % FigS8C(subj_figs,summary_data_path,nwb);
end
