%Fig2E.m
% Dynamic Table

function Fig2E(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 2e')
    
        load(strcat(summary_data_path, "\Rui_2P\totampcomb_7_10_23.mat"));
    
        R2 = vertcat(totampcomb.ampR2);
        meand = vertcat(totampcomb.meand);
        amp = vertcat(totampcomb.amp);
        depth = vertcat(totampcomb.depth);
        isdeep = depth > 150;
        sum(isdeep)
    
        shallowamp = amp(~isdeep);
        deepamp = amp(isdeep);
        shallowd = meand(~isdeep);
        deepd = meand(isdeep);
    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Shallow Diameter (um)', ...
            'data', shallowd');
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Shallow Modulation Amplitude (um)', ...
            'data', 2*shallowamp');
        col2_len = length(col2.data);
        col3 = types.hdmf_common.VectorData( ...
            'description', 'Deep Diameter (um)', ...
            'data', deepd');
        col3_len = length(col3.data);
        col4 = types.hdmf_common.VectorData( ...
            'description', 'Deep Modulation Amplitude (um)', ...
            'data',2*deepamp');
        col4_len = length(col4.data);
        table_2E = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Shallow Diameter', col1, ...
            'Shallow Modulation Amplitude', col2, ...
            'Deep Diameter',col3,...
            'Deep Modulation Amplitude',col4,...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        table_2E;
    
        nwb.analysis.set('PAModulationAmplitude2E', table_2E);
    end
end