%process_images.m
% USED TO AGGREGATE IMAGE FILES e.g. TIF INTO NWB IMAGE PLANE
% NOTE: ASSUMES PYTHON FILES IN SAME lib FOLDER & PYTHON ENVIRONMENT HAS
% DEPENDENCIES INSTALLED

function process_images(subj_id, recordings_data_file, nwb)
    % READ src_folder_directory LOCATION (EXCEL FILE)
    disp(['DEBUG PROCESSING RECORDINGS FOR: ', subj_id])
    recordings_table = readtable(recordings_data_file{1});
    
    for runnum = 1:length(recordings_table.runnum)
        disp(['READING LOCATION: ', num2str(runnum)])

        %% Add device object
        device1 = types.core.Device( ...
        'name', recordings_table.device_name(runnum), ...
        'description', recordings_table.device_description(runnum));
        nwb.general_devices.set('Imaging device',device1);

        %% Add Imaging plane object [to store images]
        % ref: https://neurodatawithoutborders.github.io/matnwb/doc/+types/+core/ImagingPlane.html
        optical_channel = types.core.OpticalChannel( ...
        'description', recordings_table.optical_channel_description(runnum), ...
        'emission_lambda', recordings_table.optical_channel_emission_lambda(runnum));
    
        imaging_plane_name = 'imaging_plane'; %name of experiment?
        imaging_plane = types.core.ImagingPlane( ...
             'optical_channel', optical_channel, ...
             'description', recordings_table.imaging_plane_description(runnum), ...
             'device', device1); %, ...
             'excitation_lambda', recordings_table.imaging_plane_exitation_lambda(runnum), ...
             'imaging_rate', recordings_table.imaging_plane_imaging_rate(runnum), ...
             'indicator', recordings_table.imaging_plane_indicator(runnum), ...
             'location', recordings_table.imaging_plane_location(runnum);
        nwb.general_optophysiology.set(imaging_plane_name, imaging_plane);
        
        recordings_location = char(recordings_table.recordings_folder(runnum));
        if recordings_table.isstack(runnum) %if already stack, recordings_folder will be tif file, not folder
            file_name = recordings_location
            file_name_py = strrep(file_name, ' ', '**'); %Work around for spaces in file names
            outvars = pyrunfile(sprintf("TiffDimDetector.py %s", file_name_py), 'numims'); %use external python file for faster processing
            ims = str2double(outvars.char)

            %Can separate loading of depths to reduce memory requirements.
            outvarsShal = pyrunfile(sprintf("TiffImReader.py %s",file_name_py), 'imsout',r1 = int16(0), r2 = int16(ims), r3 = int16(1)); 
            im_data = double(outvarsShal);
            
            % avg_ves1 = shiftdim(tmp1,1);
            % avg_ves2 = shiftdim(tmp2,1);

            clearvars -except avg_ves1 avg_ves2 files file data_folder im_size loadims animal PA depth1 depth2 pix_um rate stim_str ims pix_um
            
        else
            %% Read all images into stack (var: im_data)
            recordings_folder = char(recordings_table.recordings_folder(runnum));
            file_listing = dir(fullfile(recordings_folder, '*.tif')); %filter for TIF image files

        end
        
        
        
        % disp(['Number of TIF files found: ', num2str(length(file_listing))]);
        % if ~isempty(file_listing)
        %     disp(['Number of TIF files found: ', num2str(length(file_listing))]);
        % 
        %     % num_images = length(file_listing);
        %     % im_cell = cell(1, num_images);
        %     % 
        %     % for iter_im = 1:num_images
        %     %     try
        %     %         % Construct full file path
        %     %         full_path = fullfile(file_listing(iter_im).folder, file_listing(iter_im).name);
        %     % 
        %     %         % Read the image and store in cell array
        %     %         im_cell{iter_im} = imread(full_path);
        %     % 
        %     %         disp(['Successfully read image ', num2str(iter_im), ': ', file_listing(iter_im).name]);
        %     %     catch e
        %     %         warning(['Error reading file ', file_listing(iter_im).name, ': ', e.message]);
        %     %         im_cell{iter_im} = []; % Store empty array for failed reads
        %     %     end
        %     % end
        %     % 
        %     % %stack images along 3rd axis
        %     % im_data = cat(3, im_cell{:});
        % end

        %% Create 2Photon Series class to represent photon imaging data
        % ref: https://neurodatawithoutborders.github.io/matnwb/doc/+types/+core/TwoPhotonSeries.html
        InternalTwoPhoton = types.core.TwoPhotonSeries( ...
            'imaging_plane', types.untyped.SoftLink(imaging_plane), ...
            'data', im_data, ...
            'comments', char(recordings_table.comments(runnum)));

        nwb.acquisition.set('2pInternal', InternalTwoPhoton);

    end
    disp(['DEBUG: COMPLETED PROCESSING RECORDINGS FOR: ', subj_id])
end