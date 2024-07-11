%Fig2C.m

function Fig2C(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 2c')
    
        load(strcat(summary_data_path, "\Rui_2P\20230222 WT_PA_10\20230222PA10_5_rest_0um_allstats.mat"));
        dshallow = allstats.RadondEq_Outl;
    
        % load deep data
        load(strcat(summary_data_path, "\Rui_2P\20230222 WT_PA_10\20230222PA10_5_rest_380um_allstats.mat"));
        ddeep = allstats.RadondEq_Outl;
    
        %Create two separate with different starting times
        % Create TimeSeries
        % Must have all 3: starting_time, starting_time_rate, starting_time_unit ||
        % timestamps, timestamps_interval, timestamps_unit
    
        timeseries_shallow = nwb.acquisition.set('PAShallowTrace2C', types.core.TimeSeries('data', dshallow, 'description', 'DiameterTrace (um), comprises Fig2C with DeepTrace','data_unit','seconds',...
            'starting_time',double(0),'starting_time_rate',single(7.25),'starting_time_unit','Hz'));
        timeseries_deep = nwb.acquisition.set('PADeepTrace2C', types.core.TimeSeries('data', ddeep, 'description', 'DiameterTrace (um), comprises Fig2C with DeepTrace','data_unit','seconds',...
            'starting_time',double(0.069),'starting_time_rate',single(7.25),'starting_time_unit','Hz'));
        % disp(['Processing2C',subj_session_id])
    end
end