%Fig4C.m
% Dynamic Table

function Fig4C(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
     %DO NOT PUT UNITS IN "TYPES.HDMF_COMMON.DYNAMICTABLE", ONLY PUT UNITS
     %IN types.hdmf_common.VectorData
    if contains(subj_figs,' 4c')
        table = readtable(strcat(summary_data_path,'\IndividualFigures\Fig4\C\PiafvsK_4C.csv'));
    
        %Get all magnitude k, freq, and R2 values
        kvec = table.kvec;
        fvec = table.fvec;
    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Phase Grad (rad/mm)', ...
            'data', kvec);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Peak Vasomotor Frequency (Hz)', ...
            'data', fvec);
        table_4C = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Phase Grad', col1, ...
            'Frequency', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        table_4C;
    
        nwb.analysis.set('PiaRestfvsK4C', table_4C);

    end
end