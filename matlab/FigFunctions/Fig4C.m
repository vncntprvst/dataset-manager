%Fig4C.m
% Dynamic Table

function Fig4C(subj_figs,summary_data_path,nwb)
     %DO NOT PUT UNITS IN "TYPES.HDMF_COMMON.DYNAMICTABLE", ONLY PUT UNITS
     %IN types.hdmf_common.VectorData
    if contains(subj_figs,' 4c')
    
        %REMOVE HARD-CODING; USE summary_data_path
        % load(strcat(summary_data_path,'\AllSegments\1_30_23_Results\CombinedResults\9_4_23\pvcomb_vesselfv_tapha_01_750um_8869ves.mat'),'pvcomb')
        load("\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\VesCorrPhase\AllSegments\1_30_23_Results\CombinedResults\9_4_23\pvcomb_vesselfv_tapha_01_750um_8869ves.mat");
    
        %Get all magnitude k, freq
        kvec = abs(pvcomb(:,1));
        fvec = pvcomb(:,3);
    
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