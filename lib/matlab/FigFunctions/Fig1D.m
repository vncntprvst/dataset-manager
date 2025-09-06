%Fig1D.m
% Time Series

function Fig1D(subj_figs,summary_data_path, nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 1d')
    
        table = readtable(strcat(summary_data_path, "\IndividualFigures\Fig1\D\Fig_1D_trace_data.csv"));
        time = table.time_s;
        flux_Hz = table.flux_Hz;
        diameter_um = 2.*table.radius_um;
    
        timeseries_flux = nwb.acquisition.set('FluxTrace1D', types.core.TimeSeries('data', flux_Hz, 'description', 'FluxTrace (Hz)','data_unit','Hz',...
            'timestamps',time));
        timeseries_diameter = nwb.acquisition.set('DiameterTrace1D', types.core.TimeSeries('data', diameter_um, 'description', 'DiameterTrace (um)','data_unit','um',...
            'timestamps',time));
    end
end