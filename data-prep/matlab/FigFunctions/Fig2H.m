%Fig2H.m
% Dynamic Table

function Fig2H(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 2h')
    
        load(strcat(summary_data_path, "\Rui_2P\Pipeline\7_8_23_Analysis\CombinedCorrmat.mat")); %Load combined results (Corrmat)
        load(strcat(summary_data_path, "\Rui_2P\Pipeline\7_8_23_Analysis\CombinedKFmat.mat")); %Load combined results (KFmat)
    
        KFtodel = ~logical(CombinedKFmat(:,6));
        CombinedKFmat(KFtodel,:) = [];
    
        wts = 1./(CombinedKFmat(:,3).^2);
        kvec = abs(CombinedKFmat(:,2));
    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Phase Grad (rad_mm)', ...
            'data', abs(kvec));
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Weight 1/(rad/mm)^2', ...
            'data', wts);
        table_2H = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Phase Grad', col1, ...
            'Weight', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        table_2H;
    
        nwb.analysis.set('PAWeightVsK2H', table_2H);
    end
end