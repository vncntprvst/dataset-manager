%Fig5B.m
% Dynamic Table

function Fig5B(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,' 5b')
    
        KM1 = load(strcat(summary_data_path, "\Rui_2P\Pipeline\8_4_StimAnalysis\20221212PA7_Corr_KF_struct_stim.mat"));
        KM2 = load(strcat(summary_data_path, "\Rui_2P\Pipeline\8_4_StimAnalysis\20221208PA5_Corr_KF_struct_stim.mat"));
    
        names1 = cell2mat({KM1.Corr_KF_struct.phi_struct.PA}); KM1 = KM1.Corr_KF_struct.KFmat;
        names2 = cell2mat({KM2.Corr_KF_struct.phi_struct.PA}); KM2 = KM2.Corr_KF_struct.KFmat;
    
        % cd('\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\VesCorrPhase\Rui_2P\Pipeline\8_4_StimAnalysis')
        %KM1 = load("20221212PA7_Corr_KF_struct_stim.mat"); names1 = cell2mat({KM1.Corr_KF_struct.phi_struct.PA}); KM1 = KM1.Corr_KF_struct.KFmat;
        %KM2 = load('20221208PA5_Corr_KF_struct_stim.mat'); names2 = cell2mat({KM2.Corr_KF_struct.phi_struct.PA}); KM2 = KM2.Corr_KF_struct.KFmat;
    
        CombinedKFmat = [KM1;KM2];
        names = [names1,names2];
    
        kplot = CombinedKFmat(:,2);
        ispos = kplot > 0;
        isneg = kplot < 0;
        k_enter = abs(kplot(ispos));
        k_exit = abs(kplot(isneg));
        figure('Visible', 'off'); % Make figure invisible
        h1 = histogram(abs(kplot(ispos)),'FaceColor','r','BinWidth',0.25); hold on
        histogram(abs(kplot(isneg)),'FaceColor','b','BinWidth',0.25);
        BinEdges = h1.BinEdges;
    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'PA Stim Phase Gradient (rad/mm)', ...
            'data', kplot);
        col1_len = length(col1.data);
        table_5B_PhaseGrad = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'PA Stim Phase Gradient', col1, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        nwb.analysis.set('PAStimPhaseGradient5B', table_5B_PhaseGrad);
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Histogram Bin Edges', ...
            'data', BinEdges);
        col1_len = length(col1.data);
        table_5B_BinEdges = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Bin Edges', col1, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        nwb.analysis.set('PAStimPhaseGradientBinEdges5B', table_5B_BinEdges);
    end
end