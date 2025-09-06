
% !git clone https://urldefense.com/v3/__https://github.com/NeurodataWithoutBorders/matnwb.git__;!!Mih3wA!FgAUENkZ6VWSYw3ctjjOuSFIoSLJMI7bQHx9LG-8JQH69RKaQRagjX1e1rn7ESnDjIE7lIapCQxx1-Y-R_-5qunJ$ 
% cd 'C:\Users\dklab\matnwb'
% addpath(genpath(pwd));
 generateCore();


%#################################################################
% APP CONSTANTS (DEFAULT)

load('C:\Users\dklab\Dropbox\Work_related\Amalia_LAbchart_Miniproject\whisking_Breathing\NewDataset\Ammonia\Ammonia with latency\Data_S2_ABC.mat')
load('C:\Users\dklab\Dropbox\Work_related\Amalia_LAbchart_Miniproject\whisking_Breathing\NewDataset\Ammonia\Ammonia with latency\Data_S2_DEF.mat')
output_path = "Z:\U19\Deschenes_Group\Grimace ammonia\output2\"; %NWB file written to this location
%#################################################################

%PRE-PROCESSING / PREREQUISITES
% Check if output_path exists, create it if not
if ~exist(output_path, 'dir')
    mkdir(output_path);
end
warning('off','all')

%% creat Nwb file
thesedate2 = [[2022 12 20 12 00 00 ]; [2022 12 20 12 00 00]; [2022 12 15 12 00 00];[2022 12 15 12 00 00]];
% 'Data2022_12_20_Session_2','Data2022_12_20_Session_1','Date2022_12_15_block8','Date2022_12_15'
thesedate = [[2022 04 29 12 00 00 ]; [2022 05 30 12 00 00]; [2022 05 30 12 00 00];[2022 08 10 12 00 00]];

for i=2:5
    thissession= Dataall{i};
nwb = NwbFile( ...
    'session_description', 'Muralis unit response to Ammonia stimulation in anesthetized rat',...
    'identifier', ['Rat' num2str(i)], ...
'session_start_time', datetime( thesedate(i-1,:), 'TimeZone', 'local'));
% sessionStartTime = datetime('2022-04-29T00:00:00', 'TimeZone', 'America/New_York');

% nwb.session_start_time = sessionStartTime;

%% here to add vector data for trials such as true false, left right, start end and so on....

trials = types.core.TimeIntervals( ...
    'colnames', {'start_time','stop_time'}, ...
    'description', 'trial data and properties', ...
    'id', types.hdmf_common.ElementIdentifiers('data', 0:numel(thissession.AmoniaStim.onset)-1), ...
    'start_time', types.hdmf_common.VectorData( ...
        'data', [thissession.AmoniaStim.onset], ...
   	    'description','start time of ammonia stimulation in samples FS_2k'), 'stop_time', types.hdmf_common.VectorData( ...
        'data', [thissession.AmoniaStim.onset+2e4], ...
   	    'description','start time of ammonia stimulation in samples FS_2k'));
nwb.intervals_trials = trials;



% Assuming you have a list of stimulus onset times (in seconds)
% stimulusOnsetTimes = [0.5, 1.0, 1.5, 2.0]; % Modify this with your actual data

% Add stimulus onset times to your NWB data structure (e.g., DynamicTable)
% nwbFile.acquisition.get('<your_data_structure>').addColumn('stimulus_onset_times', 'Stimulus onset times for each trial', stimulusOnsetTimes);
%% add hehavior in this case breathing  (whisker and ....)

% Create a datetime object with a specific timezone (e.g., US/Pacific)




behavior_processing_module = types.core.ProcessingModule('description', 'stores behavioral data.');
nwb.processing.set("behavior", behavior_processing_module);



time_series = types.core.TimeSeries( ...
    'data', thissession.Breathing.pks, ...
    'timestamps', thissession.Breathing.Locations, ...
    'description', 'The voltage value and the timestamp of inspiration', ...
    'data_unit', 'seconds' ...
);
 
behavioral_events = types.core.BehavioralEvents();
behavioral_events.timeseries.set('lever_presses', time_series);
 
%behavior_processing_module = types.core.ProcessingModule("stores behavioral data.");  % if you have not already created it
behavior_processing_module.nwbdatainterface.set('BehavioralEvents', behavioral_events);
% nwb.processing.set('behavior', behavior_processing_module); % if you have not already added it

%%  add spikes
theseneurons = thissession.Spike.labels(ismember(thissession.Spike.labels(:,2),[  2 3 ]),1);

% thissession.Spike.spiketimes(thissession.Spike.labels


 num_cells = numel(theseneurons);
  firing_rate = 20;

spikes = cell(1, num_cells);
for iShank = 1:num_cells
    spikes{iShank} = double(thissession.Spike.spiketimes(thissession.Spike.assigns==theseneurons(iShank)));
end



[spike_times_vector, spike_times_index] = util.create_indexed_column(spikes);
 
nwb.units = types.core.Units( ...
    'colnames', {'spike_times'}, ...
    'description', 'units table', ...
    'id', types.hdmf_common.ElementIdentifiers( ...
        'data', int64(0:length(spikes) - 1) ...
    ), ...
    'spike_times', spike_times_vector, ...
    'spike_times_index', spike_times_index ...
);

% Define the path to save the NWB file
nwbFilePath = ['Z:\U19\Deschenes_Group\Grimace ammonia\output2\Electrophys' num2str(i) '.nwb'];

% Write the NWB file to the specified path
nwbExport(nwb, nwbFilePath);

end


for i=2:5
    thissession= Dataall2{i};
nwb = NwbFile( ...
    'session_description', 'Muralis unit response to Ammonia stimulation in anesthetized rat',...
    'identifier', ['Rat' num2str(i+5)], ...
'session_start_time', datetime( thesedate2(i-1,:), 'TimeZone', 'local'));
% sessionStartTime = datetime('2022-04-29T00:00:00', 'TimeZone', 'America/New_York');

% nwb.session_start_time = sessionStartTime;

%% here to add vector data for trials such as true false, left right, start end and so on....

trials = types.core.TimeIntervals( ...
    'colnames', {'start_time','stop_time'}, ...
    'description', 'trial data and properties', ...
    'id', types.hdmf_common.ElementIdentifiers('data', 0:numel(thissession.AmoniaStim.onset)-1), ...
    'start_time', types.hdmf_common.VectorData( ...
        'data', [thissession.AmoniaStim.onset], ...
   	    'description','start time of ammonia stimulation in samples FS_2k'), 'stop_time', types.hdmf_common.VectorData( ...
        'data', [thissession.AmoniaStim.onset+2e4], ...
   	    'description','start time of ammonia stimulation in samples FS_2k'));
nwb.intervals_trials = trials;



% Assuming you have a list of stimulus onset times (in seconds)
% stimulusOnsetTimes = [0.5, 1.0, 1.5, 2.0]; % Modify this with your actual data

% Add stimulus onset times to your NWB data structure (e.g., DynamicTable)
% nwbFile.acquisition.get('<your_data_structure>').addColumn('stimulus_onset_times', 'Stimulus onset times for each trial', stimulusOnsetTimes);
%% add hehavior in this case breathing  (whisker and ....)

% Create a datetime object with a specific timezone (e.g., US/Pacific)




behavior_processing_module = types.core.ProcessingModule('description', 'stores behavioral data.');
nwb.processing.set("behavior", behavior_processing_module);



time_series = types.core.TimeSeries( ...
    'data', thissession.Breathing.pks, ...
    'timestamps', thissession.Breathing.Locations, ...
    'description', 'The voltage value and the timestamp of inspiration', ...
    'data_unit', 'seconds' ...
);
 
behavioral_events = types.core.BehavioralEvents();
behavioral_events.timeseries.set('lever_presses', time_series);
 
%behavior_processing_module = types.core.ProcessingModule("stores behavioral data.");  % if you have not already created it
behavior_processing_module.nwbdatainterface.set('BehavioralEvents', behavioral_events);
% nwb.processing.set('behavior', behavior_processing_module); % if you have not already added it

%%  add spikes
theseneurons = thissession.Spike.labels(ismember(thissession.Spike.labels(:,2),[  2 3 ]),1);

% thissession.Spike.spiketimes(thissession.Spike.labels


 num_cells = numel(theseneurons);
  firing_rate = 20;

spikes = cell(1, num_cells);
for iShank = 1:num_cells
    spikes{iShank} = double(thissession.Spike.spiketimes(thissession.Spike.assigns==theseneurons(iShank)));
end



[spike_times_vector, spike_times_index] = util.create_indexed_column(spikes);
 
nwb.units = types.core.Units( ...
    'colnames', {'spike_times'}, ...
    'description', 'units table', ...
    'id', types.hdmf_common.ElementIdentifiers( ...
        'data', int64(0:length(spikes) - 1) ...
    ), ...
    'spike_times', spike_times_vector, ...
    'spike_times_index', spike_times_index ...
);

    %% Final export start
    nwbExport(nwb, fullfile(output_path, ['Electrophys' num2str(i+5) '.nwb']));
    clearvars nwb

end
