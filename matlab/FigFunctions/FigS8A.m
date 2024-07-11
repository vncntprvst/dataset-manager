%FigS8A.m
% Dynamic Table

function FigS8A(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' S8a')
    
        %load(strcat(summary_data_path,'\AllSegments\ShortDistAnalysis\Supp8\ExamplePhaseProg_20Mar2020_170741_TB013120M4_Ves91_FullDistAndPhase.mat'));
        load("Y:\DataAnalysis\VesCorrPhase\AllSegments\ShortDistAnalysis\Supp8\ExamplePhaseProg_20Mar2020_170741_TB013120M4_Ves91_FullDistAndPhase.mat");
        
        phase = plotstruct(1).fullphase;
        dist = plotstruct(1).fulldist;
        %Assign to dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Distance (mm)', ...
            'data', dist);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Vessel Phase (rad)', ...
            'data', phase);
        table_S8A_Pts = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Distance', col1, ...
            'Vessel Phase', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        nwb.analysis.set('VascularPhaseProgressionS8A', table_S8A_Pts);
    
    end
end