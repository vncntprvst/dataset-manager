%FigS4B.m
%JD230523R1495trials_011524_ROI_010_00001
% Z:\Jacob\Flux\DKLab\JDRLXJ\visualization\SuppFig
% TBRLBB_post_processing_single_frame_ReaChR.m

function FigS4B(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' S4b')
        
        table = readtable(strcat(summary_data_path,'\IndividualFigures\FigS4\B\Supp4B_FullTraces.csv'));
    
        time = table.time;
        flux_Hz = table.flux_trace;
        diameter_um = table.diam_trace;
    
        timeseries_flux = nwb.acquisition.set('FluxTraceReaChRS4B', types.core.TimeSeries('data', flux_Hz, 'description', 'FluxTrace (Hz)','data_unit','Hz',...
            'timestamps',time));
        timeseries_diameter = nwb.acquisition.set('DiamTraceReaChRS4B', types.core.TimeSeries('data', diameter_um, 'description', 'DiameterTrace (um)','data_unit','um',...
            'timestamps',time));
    end
end