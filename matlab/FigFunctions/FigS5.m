%FigS5.m
% Dynamic Table

function FigS5(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' S5')
    
        corr_tbl = readtable(strcat(summary_data_path, '\IndividualFigures\FigS5\FigS5_ScatterData.csv'));
    
        dist_pts = corr_tbl.dist;
        corr_pts = corr_tbl.correlation;
        %             figure; scatter(dist_pts,corr_pts,'filled');
    
        %Assign to dynamic table: Pia
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Median pair distance in bin (mm)', ...
            'data', dist_pts);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Average travel direction correlation in bin', ...
            'data', corr_pts);
        table_S5_Pts = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Median pair distance (mm)', col1, ...
            'Average correlation', col2, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        nwb.analysis.set('PATravelDirectionCorrelationS5', table_S5_Pts);
    end
end