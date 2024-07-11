%Fig5A.m

function Fig5A(subj_figs,summary_data_path,nwb)
if contains(subj_figs,' 5a')

    %avoid hard-coding:
    % addpath(genpath('\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\chronux_2_12'))
    % addpath(genpath('\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\chronux_2_12'))
    % addpath('\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\VesCorrPhase\ExtractPGCode')

    stimstats1 = load(strcat(summary_data_path, "\Rui_2P\20221212 WT_PA_7\20221212PA7_PA2_stim_0um_allstats.mat"));
    stimstats2 = load(strcat(summary_data_path, "\Rui_2P\20221212 WT_PA_7\20221212PA7_PA2_stim_390um_allstats.mat"));

    %stimstats1 = load("Y:\DataAnalysis\VesCorrPhase\Rui_2P\20221212 WT_PA_7\20221212PA7_PA2_stim_0um_allstats.mat");
    %stimstats2 = load("Y:\DataAnalysis\VesCorrPhase\Rui_2P\20221212 WT_PA_7\20221212PA7_PA2_stim_390um_allstats.mat");

    stimstats1 = stimstats1.allstats;
    stimstats2 = stimstats2.allstats;

    try
        rate = stimstats1.rate;
    catch
        rate = 7.25;
    end
    waves = stimstats1.RadondEq_Outl;
    waves = waves - mean(waves);
    waved = stimstats2.RadondEq_Outl;
    waved = waved - mean(waved);
    times = stimstats1.time;
    timed = stimstats2.time;
    if sum(times - timed) == 0
        timed = timed + (1/rate)/2;
    end

    %Interpolate each signal to get equal time points
    tqs = times(1):(1/(2*rate)):times(end);
    tqd = timed(1):(1/(2*rate)):timed(end);
    waves_q_tmp = interp1(times,waves,tqs);
    waved_q_tmp = interp1(timed,waved,tqd);

    %Delete first wave1 value so that both start at t=0.75.
    waves_q = waves_q_tmp(2:end);
    tqs = tqs(2:end);
    %Delete last wave1 value to make both time series the same duration
    waved_q = waved_q_tmp;
    waved_q(end) = [];
    tqd(end) = [];

    params.Fs = rate*2; %Interpolated rate is twice actual single depth rate
    params.pad = 2;
    params.fpass = [0 params.Fs/4]; %Hz, default is [0 Fs/2]
    params.err   = [2 .05];
    params.trialave = 0;
    T = stimstats1.time(end);
    BW = 0.02; %600s trial -> TBW =~ 12
    params.tapers = [round(T*BW),round(2*T*BW-1)]; %Time-BW product and number of tapers
    addpath(genpath('\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\chronux_2_12'))

    params.err = [2,0.05];
    [~,phi_stim,~,Ss_stim,Sd_stim,f_stim,~,phistd_stim,~] = coherencyc(waved_q,waves_q,params);


    figure; plot(f_stim,log10(Ss_stim),'b'); xlim([0 1]); xlabel('Frequency (Hz)','Interpreter','latex'); ylabel('Log10(Power)','Interpreter','latex');
    title('20221212WT7 PA2 stim','Interpreter','latex');
    % savefig('20221212WT7_PA2_stim_Shallow.fig');
    % print(gcf,'20221212WT7_PA2_stim_Shallow','-depsc2','-r0')
    figure; plot(f_stim,log10(Sd_stim),'b'); xlim([0 1]); xlabel('Frequency (Hz)','Interpreter','latex'); ylabel('Log10(Power)','Interpreter','latex');
    title('20221212WT7 PA2 stim','Interpreter','latex');
    figure
    plot(f_stim,phi_stim,'b'); xlim([0 1]); ylim([-pi pi]); hold on
    plot(f_stim,phi_stim + phistd_stim','Color',[0,0,1,0.2]);
    plot(f_stim,phi_stim - phistd_stim','Color',[0,0,1,0.2]); yline(0);
    xlim([0 0.5]); ylim([-pi/2 pi/2]);
    yticks([-pi/2 -pi/4 0 pi/4 pi/2]);
    yticklabels({'-$\pi$/2', '-$\pi$/4','0', '-$\pi$/4', '$\pi$/2'});
    set(gca,'TickLabelInterpreter','latex');

    %Create dynamic table
    col1 = types.hdmf_common.VectorData( ...
        'description', 'Frequency (Hz)', ...
        'data', f_stim');
    col1_len = length(col1.data);
    col2 = types.hdmf_common.VectorData( ...
        'description', 'Phase (rad)', ...
        'data', phi_stim);
    col3 = types.hdmf_common.VectorData( ...
        'description', 'Phase SD (rad)', ...
        'data', phistd_stim');
    table_5A_phase = types.hdmf_common.DynamicTable( ...
        'description', 'analysis table', ...
        'Frequency', col1, ...
        'Phase', col2, ...
        'Phase SD',col3,...
        'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
        );
    nwb.analysis.set('PAStimPhase5A', table_5A_phase);


    % calc and plot resid spectrum
    stimstats1 = load(strcat(summary_data_path, "\Rui_2P\20221212 WT_PA_7\20221212PA7_PA2_stim_0um_allstats.mat"));

    %stimstats1 = load("Y:\DataAnalysis\VesCorrPhase\Rui_2P\20221212 WT_PA_7\20221212PA7_PA2_stim_0um_allstats.mat");

    stimstats1 = stimstats1.allstats;
    rate = 7.25; %Hz
    waves = stimstats1.RadondEq_Outl;
    waves = waves - mean(waves);
    params.Fs = rate; %Interpolated rate is twice actual single depth rate
    params.pad = 2;
    params.fpass = [0 params.Fs/4]; %Hz, default is [0 Fs/2]
    params.err   = [2 .05];
    params.trialave = 0;
    T = stimstats1.time(end);
    BW = 0.02; %600s trial -> TBW =~ 12
    params.tapers = [round(T*BW),round(2*T*BW-1)]; %Time-BW product and number of tapers
    addpath(genpath('\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\chronux_2_12'))
    addpath('\\dk-server.dk.ucsd.edu\jaduckwo\DataAnalysis\VesCorrPhase\ExtractPGCode')

    [data_nolines,f,Sresid,Stot,Amps,fmax] = ResidSpec(waves,params);
    A = abs(cell2mat(Amps)).^2;
    A = A./(2*BW); %Divide by full bandwidth to get line height
    xlocs = f(struct2array(fmax))';
    ylocs = Sresid(struct2array(fmax));
    U = zeros(length(xlocs),1);
    V = A;
    figure; plot(f,Stot,'k'); hold on; plot(f,Sresid,'b'); xlim([0 0.5]);
    quiver(xlocs,ylocs,U,V,'off','LineWidth',2,'ShowArrowHead','off')
    ax = gca;
    ax.TickLabelInterpreter = 'latex';
    set(ax,'YScale','log');
    ylim([0.01,10]);
    ylabel('log10(Power)','Interpreter','latex'); xlabel('Freq (Hz)','Interpreter','latex');

    %Create dynamic table
    col1 = types.hdmf_common.VectorData( ...
        'description', 'Frequency (Hz)', ...
        'data', f');
    col1_len = length(col1.data);
    col2 = types.hdmf_common.VectorData( ...
        'description', 'Shallow PA Residual Power', ...
        'data', Sresid);
    table_5A_spectrum = types.hdmf_common.DynamicTable( ...
        'description', 'analysis table', ...
        'Frequency', col1, ...
        'Phase', col2, ...
        'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
        );
    nwb.analysis.set('PAStimSpectrum5A', table_5A_spectrum);
    %Create dynamic table
    col1 = types.hdmf_common.VectorData( ...
        'description', 'Extracted Freqs (Hz)', ...
        'data', xlocs);
    col1_len = length(col1.data);
    col2 = types.hdmf_common.VectorData( ...
        'description', 'Shallow PA Residual Power at Extracted Freqs', ...
        'data', ylocs);
    col3 = types.hdmf_common.VectorData( ...
        'description', 'Shallow PA Extracted Power at Extracted Freqs', ...
        'data', V);
    table_5A_extractedpower = types.hdmf_common.DynamicTable( ...
        'description', 'analysis table', ...
        'Extracted Frequency', col1, ...
        'Residual Power', col2, ...
        'Extracted Power',col3,...
        'id', types.hdmf_common.ElementIdentifiers('data', linspace(1,col1_len,col1_len)) ...
        );
    nwb.analysis.set('PAStimExtractedPower5A', table_5A_extractedpower);
end
end