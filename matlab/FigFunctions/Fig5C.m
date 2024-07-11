%Fig5C.m
% Dynamic Table

function Fig5C(subj_figs,summary_data_path,nwb)
    if contains(subj_figs,' 5c')
    
        %REMOVE HARD-CODING; USE summary_data_path
        %cd(strcat(summary_data_path,'\AllSegments\StimRegCoh\1_30_23_Analysis\StimRegPhase'))
        cd('Y:\DataAnalysis\VesCorrPhase\AllSegments\StimRegCoh\1_30_23_Analysis\StimRegPhase');
        files = dir('*StimRegPhase.mat');
    
        %Combine results from all animals
        for i = 1:length(files)
            load(files(i).name);
            if i == 1
                k_fs = SRP.k_fs;
                k_fs2 = SRP.k_fs2;
                f_fs = SRP.f_fs;
                f_fs2 = SRP.f_fs2;
                R_fs = SRP.R_fs;
                R_fs2 = SRP.R_fs2;
                lengths = SRP.lengths;
                segs = SRP.segs;
            else
                k_fs = [k_fs;SRP.k_fs];
                k_fs2 = [k_fs2;SRP.k_fs2];
                f_fs = [f_fs;SRP.f_fs];
                f_fs2 = [f_fs2;SRP.f_fs2];
                R_fs = [R_fs;SRP.R_fs];
                R_fs2 = [R_fs2;SRP.R_fs2];
                lengths = [lengths;SRP.lengths];
                segs = [segs;SRP.segs];
            end
            i;
        end
    
        lengthtodel = lengths < 0.75;
        nantodel = isnan(k_fs);
        todel = or(lengthtodel,nantodel);
    
        k_fs(todel) = [];
        k_fs2(todel) = [];
        f_fs(todel) = [];
        f_fs2(todel) = [];
        R_fs(todel) = [];
        R_fs2(todel) = [];
        lengths(todel) = [];
        segs(todel) = [];
    
        lengthsfs = lengths;
        segsfs = segs;
        lengthsfs2 = lengths;
        segsfs2 = segs;
    
        %Calculate t-test statistic
        alpha = 0.01; %Set significance level
        p = 1-alpha;
        p2 = 1-alpha/2;
        t_mat = zeros(length(R_fs),1);
        for i = 1:length(R_fs)
            r = R_fs(i);
            n = segsfs(i);
            df = n-2;
            if df > 0
                SE = sqrt((1-r^2)/(n-2));
                t = r/SE;
                tcrit = icdf('T',p2,df);
                t_mat(i) = t;
                t_mat(i,2) = tcrit;
            else
                t_mat(i,1) = NaN;
                t_mat(i,2) = NaN;
            end
        end
        t_todel = zeros(size(t_mat,1),1);
        for i=1:length(t_todel)
            if abs(t_mat(i,1))<t_mat(i,2) %If t<tcrit
                t_todel(i) = 1;
            end
        end
        t_todel = logical(t_todel);
        k_fs(t_todel) = [];
        f_fs(t_todel) = [];
        R_fs(t_todel) = [];
        lengthsfs(t_todel) = [];
        segsfs(t_todel) = [];
    
        %Here we consider only stim frequencies less than 0.2 Hz, the intrinsic
        %frequency range of these arteries
        f_lessthan_2Hz = f_fs < 0.2;
        %Get all magnitude k, freq, and R^2 values
        kplot = abs(k_fs(f_lessthan_2Hz));
        fplot = f_fs(f_lessthan_2Hz);
        wts = R_fs(f_lessthan_2Hz).^2;
    
        %Create dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Pia Stim Phase Gradient (rad/mm)', ...
            'data', kplot);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Pia Stim Frequency (Hz)', ...
            'data', fplot);
        col3 = types.hdmf_common.VectorData( ...
            'description', 'Pia Stim Weights, Phase Gradient R2', ...
            'data', wts);
        table_5C_FvsK = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Phase Gradient ', col1, ...
            'Frequency', col2, ...
            'Weights, R2',col3,...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        nwb.analysis.set('PiaStimFvsK5C', table_5C_FvsK);
    
    end
end