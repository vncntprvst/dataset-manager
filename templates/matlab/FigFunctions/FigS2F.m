%FigS2F.m
% Dynamic Table

function FigS2F(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' S2f')
    
        openfig(strcat(summary_data_path,'\IndividualFigures\FigS2\DKLab_TBRLBB_dq_vs_q_fit_med_PA_data.fig'))
        
        h = findobj(gca,'Type','scatter');
        x=get(h,'Xdata');
        y=get(h,'Ydata');
    
        col1 = types.hdmf_common.VectorData( ...
            'description', 'PA Average Flux (Hz)', ...
            'data', x);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'PA Change in Flux (Hz)', ...
            'data', y);
        table_S2F_Dq = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'PA Average Flux (Hz)', col1, ...
            'PA Change in Flux (Hz)', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
    
        nwb.analysis.set('PARawChangeinFluxVsFluxS2F', table_S2F_Dq);
        close all;
    end
end