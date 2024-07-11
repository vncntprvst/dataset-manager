%Fig4D.m
% Dynamic Table

function Fig4D(subj_figs,summary_data_path,nwb)
if contains(subj_figs,' 4d')

    %load(strcat(summary_data_path,'\AllSegments\PhaseAreaAnalysis\partition_k.mat'),'partition_k')
    load("\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\VesCorrPhase\AllSegments\PhaseAreaAnalysis\partition_k.mat");

    trial_var = partition_k.trial_var;

    avgk = trial_var(:,4);
    dk = trial_var(:,1);
    nantodel = isnan(avgk);
    avgk(nantodel) = [];
    dk(nantodel) = [];
    xpts = avgk(avgk < 0.6);
    ypts = dk(avgk < 0.6);

    %Create dynamic table
    col1 = types.hdmf_common.VectorData( ...
        'description', 'Trial Average Phase Grad (rad/mm)', ...
        'data', xpts);
    col1_len = length(col1.data);
    col2 = types.hdmf_common.VectorData( ...
        'description', 'Trial Phase Grad Standard Deviation (rad/mm)', ...
        'data', ypts);
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