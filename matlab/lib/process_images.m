%process_images.m
% USED TO AGGREGATE IMAGE FILES e.g. TIF INTO NWB IMAGE PLANE

function process_images(subj_id, recordings_data_file, nwb)
    % READ src_folder_directory LOCATION (EXCEL FILE)
    disp(['PROCESSING RECORDINGS FOR: ', subj_id])
    img_location = readtable(recordings_data_file{1});
    
    %for runnum = 1:length(img_location.runnum)
    for runnum = 1:1
        disp(['READING LOCATION: ', num2str(runnum)])
    end

     % how much of this info is in meta data text file?
     imaging_plane_name = 'imaging_plane'; %name of experiment?
     imaging_plane = types.core.ImagingPlane( ...
         'optical_channel', 'GFP', ...
         'description', 'pial and penetrating arterioles and veins', ...
         'device', device1); %, ...
         % 'excitation_lambda', 0, ...
         % 'imaging_rate', 5., ...
         % 'indicator', 'GFP', ...
         % 'location', 'my favorite brain location');
% 
%     % process_images(src_folder_directory, imaging_plane, nwb) 
%     %pass by reference to imageing_plane? Commented out for testing 7/10/24 JD
% 
%     % nwb.general_optophysiology.set(imaging_plane_name, imaging_plane);
% 
% 
% 
% 
% 
% 
%     % READ src_folder_directory LOCATION (EXCEL FILE)
%     % LOOP THROUGH EXCEL FILENAMES
%     % READ IMAGE FILE
%     % STORE IN NWB FORMAT
% 
%     disp(['READING LOCATION: ', src_folder_directory])
%     img_location = readtable(src_folder_directory{1});
% 
%     % for runnum = 1:length(img_location.runnum)
%     runnum = 1;
% disp(['READING LOCATION: ', runnum])
% 
%         % TODO: read meta-data file for NWB
% 
%         current_folder = img_location.folder{runnum};
%         tif_files = dir(fullfile(current_folder, '*.tif'));
%         im1 = imread([tif_files(1).folder,'\',tif_files(1).name]);
%         array_size = zeros(size(im1,1),size(im1,2),length(tif_files));
% 
%         ds = datastore(current_folder,"FileExtensions",".tif",'Type', 'image');
%         img_data = tall(ds); %Need to "gather" the tall array before saving to nwb. Try using "matfile" instead. OR Process on computer with larger memory.
% 
%         % disp(['TIF files in folder: ' current_folder]);
%         % for i = 1:length(tif_files)
%         %     disp(tif_files(i).name);
%         % end
%         % disp(' ');
% 
%         % Define a file path for temporary storage
%         temp_file = 'temp_image_data.mat';
%         % Initialize matfile for writing
%         matObj = matfile(temp_file, 'Writable', true);
%         matObj.image_data = zeros(array_size, 'single'); % Adjust data type if needed
% 
% 
% 
%     % end
% 
% 
% 
%     %data will be array for image
%     % img_data = ones(200, 100, 1000)
% 
% 
%     InternalTwoPhoton = types.core.TwoPhotonSeries( ...
%     'imaging_plane', imaging_plane, ...
%     'starting_time', 0.0, ...
%     'starting_time_rate', 3.0, ...
%     'data', img_data); % , ...
%     % 'data_unit', 'lumens');
% 
% nwb.acquisition.set('2pInternal', InternalTwoPhoton);
%     %return imaging_plane
end