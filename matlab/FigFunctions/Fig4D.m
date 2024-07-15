%Fig4D.m

function Fig4D(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 4d')
        clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    
        table = readtable(strcat(summary_data_path,'\IndividualFigures\Fig4\D\PiaDKvsAvgK_4D.csv'));
    
        %Get all magnitude k, freq, and R2 values
        avgk = table.avgk;
        dk = table.dk;
    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Trial Average Phase Grad (rad/mm)', ...
            'data', avgk);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Trial Phase Grad Standard Deviation (rad/mm)', ...
            'data', dk);
        table_4D = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Average Phase Grad', col1, ...
            'Phase Grad SD', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        table_4D;
    
        nwb.analysis.set('PiaRestDKvsK4D', table_4D);
    end
end