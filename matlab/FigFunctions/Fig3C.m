%Fig3C.m
% Dynamic Table

function Fig3C(subj_figs,summary_data_path,nwb)
if contains(subj_figs,' 3c')

    %REMOVE HARD-CODING; USE summary_data_path
    load("\\dk-server.dk.ucsd.edu\jaduckwo\Rui_2P_DataBackup\JD_GC_Diam2P\6_13_23\7_24Analysis\roi10\resultsmat_sf3.mat");

    %Average time series (Ca and FWHM) with GCaMP axis flipped
    time = resultsmat.time;
    diam = resultsmat.diam;
    wave = resultsmat.wave;
    avgdiam = mean(diam,1)';
    avgwave = mean(wave,1)';
    timeseries_diam = nwb.acquisition.set('DiameterAverageTrace3C', types.core.TimeSeries('data', avgdiam, 'description', 'Diameter Trace (um)','data_unit','um',...
        'timestamps',time))
    timeseries_Ca = nwb.acquisition.set('CalciumAverageTrace3C', types.core.TimeSeries('data', avgwave, 'description', 'GCaMP8.1 Signal Trace (df/f)','data_unit','df/f',...
        'timestamps',time))
end
end