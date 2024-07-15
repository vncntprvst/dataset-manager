%Fig3C.m

function Fig3C(subj_figs,summary_data_path,nwb)
if contains(subj_figs,' 3c')
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path

    table = readtable(strcat(summary_data_path,'\IndividualFigures\Fig3\C\AvgCaDiameter_3C.csv'));

    %Average time series (Ca and FWHM) with GCaMP axis flipped
    time = table.time;
    avgdiam = table.avgdiam;
    avgwave = table.avgwave;
    timeseries_diam = nwb.acquisition.set('DiameterAverageTrace3C', types.core.TimeSeries('data', avgdiam, 'description', 'Diameter Trace (um)','data_unit','um',...
        'timestamps',time))
    timeseries_Ca = nwb.acquisition.set('CalciumAverageTrace3C', types.core.TimeSeries('data', avgwave, 'description', 'GCaMP8.1 Signal Trace (df/f)','data_unit','df/f',...
        'timestamps',time))
end
end