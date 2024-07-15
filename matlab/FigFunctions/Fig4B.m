%Fig4B.m
% Dynamic Table

function Fig4B(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 4b')
    
        table = readtable(strcat(summary_data_path,'\IndividualFigures\Fig4\B\PiaR2vsK_4B.csv'));
        
        %Get all magnitude k, freq, and R2 values
        kvec = table.kvec;
        r2vec = table.r2vec;

    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Phase Grad (rad/mm)', ...
            'data', kvec);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Phase Grad Fit R2', ...
            'data', r2vec);
        table_4B = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Phase Grad', col1, ...
            'R2', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
    
        nwb.analysis.set('PiaRestR2vsK4B', table_4B);
    end
end