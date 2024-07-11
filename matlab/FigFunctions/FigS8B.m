%FigS8B.m
% Dynamic Table

function FigS8B(subj_figs,summary_data_path,nwb)
    clearvars -except subj_session_id summary_data_path subj_figs primary_experiments_table subj nwb output_path
    if contains(subj_figs,'S8b')
        
        load(strcat(summary_data_path,'\AllSegments\ShortDistAnalysis\alpha0_01\files_allspeeds.mat'));
        % load("Y:\DataAnalysis\VesCorrPhase\AllSegments\ShortDistAnalysis\alpha0_01\files_allspeeds.mat");
    
        for i = 1:length(files)
            files(i).meanlength = mean(files(i).all_length);
            minlen(i) = min(files(i).all_length);
            maxlen(i) = max(files(i).all_length);
        end
        lengths = [files.meanlength];
        speed = [files.speed];
        speedSE = [files.speedSE];
        lengthlowerlim = lengths - minlen;
        lengthupperlim = maxlen - lengths;
        colormat = zeros(length(lengths),3);
        colormat(:,3) = 1;
    
        figure
        errorbar(lengths,speed,speedSE,speedSE,lengthlowerlim,lengthupperlim,"o",'LineWidth',1,'Color','k');
        hold on;
        scatter(lengths,speed,25,colormat,'filled');
        xlabel('Average vessel length analyzed (mm)','Interpreter','latex');
        ylabel('$Ca^{2+}$ wave speed (from $f$ vs $|k|$ fit)','Interpreter','latex');
        title({'$Ca^{2+}$ wave speeds calculated on different vessel segment lengths','Red = our full dataset ($>$0.75mm), Blue = Shorter vessel segments chosen randomly'},'Interpreter','latex');
        xlim([0 2]); ylim([0.5 2.5]);
    
        %Assign to dynamic table
        col1 = types.hdmf_common.VectorData( ...
            'description', 'Mean Distance (mm)', ...
            'data', lengths);
        col1_len = length(col1.data);
        col2 = types.hdmf_common.VectorData( ...
            'description', 'Speed (mm/s)', ...
            'data', speed);
        col3 = types.hdmf_common.VectorData( ...
            'description', 'Speed SE (mm/s)', ...
            'data', speedSE);
        col4 = types.hdmf_common.VectorData( ...
            'description', 'Length Lower Limit (mm)', ...
            'data', lengthlowerlim);
        col5 = types.hdmf_common.VectorData( ...
            'description', 'Length Upper Limit (mm)', ...
            'data', lengthupperlim);
        table_S8B_Pts = types.hdmf_common.DynamicTable( ...
            'description', 'analysis table', ...
            'Distance (mm)', col1, ...
            'Vessel Phase (rad)', col2, ...
            'Speed SE (rad)', col3, ...
            'Length Lower Limit (mm)', col4, ...
            'Length Upper Limit (mm)', col5, ...
            'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
            );
        nwb.analysis.set('VascularWaveSpeedsatDifferentLengthsS8B', table_S8B_Pts);
    end
end