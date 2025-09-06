%Fig2F.m
% Dynamic Table

function Fig2F(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 2f')
    
        load(strcat(summary_data_path, "\Rui_2P\Pipeline\7_8_23_Analysis\CombinedCorrmat.mat")); %Load combined results (Corrmat)
        load(strcat(summary_data_path, "\Rui_2P\Pipeline\7_8_23_Analysis\CombinedKFmat.mat")); %Load combined results (KFmat)
        
        KFtodel = ~logical(CombinedKFmat(:,6));
        CombinedKFmat(KFtodel,:) = [];
    
        kvec = abs(CombinedKFmat(:,2));
        fvec = CombinedKFmat(:,1);
    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Phase Grad (rad/mm)', ...
            'data', kvec);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Frequency (Hz)', ...
            'data', fvec);
        table_2F = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Phase Grad', col1, ...
            'freq', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        table_2F;
    
        nwb.analysis.set('PAFvsK2F', table_2F);
    end
end