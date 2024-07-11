%Fig4B.m
% Dynamic Table

function Fig4B(subj_figs,summary_data_path,nwb)
    if contains(subj_figs,' 4b')
    
        %REMOVE HARD-CODING; USE summary_data_path
        % load(strcat(summary_data_path,'\AllSegments\1_30_23_Results\CombinedResults\9_4_23\pvcomb_vesselfv_tapha_01_750um_8869ves.mat'),'pvcomb');
        load("\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\VesCorrPhase\AllSegments\1_30_23_Results\CombinedResults\9_4_23\pvcomb_vesselfv_tapha_01_750um_8869ves.mat");
    
        %Get all magnitude k, freq, and R2 values
        kvec = abs(pvcomb(:,1));
        r2vec = pvcomb(:,2).^2;
    
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