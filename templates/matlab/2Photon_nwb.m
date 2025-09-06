%2Photon_nwb.m

%#################################################################
% APP CONSTANTS (DEFAULT)

load('C:\Users\dklab\Dropbox\Work_related\Amalia_LAbchart_Miniproject\whisking_Breathing\NewDataset\Ammonia\Ammonia with latency\Data_S2_ABC.mat')
load('C:\Users\dklab\Dropbox\Work_related\Amalia_LAbchart_Miniproject\whisking_Breathing\NewDataset\Ammonia\Ammonia with latency\Data_S2_DEF.mat')
output_path = "Z:\U19\Deschenes_Group\Grimace ammonia\output2\"; %NWB file written to this location
%#################################################################

%PRE-PROCESSING / PREREQUISITES
% Check if output_path exists, create it if not
if ~exist(output_path, 'dir')
    mkdir(output_path);
end
warning('off','all')


% 17-JUL-2024 WIP; CALLS tiffMap.m (lib folder)
% EXTRACTS HEADER DATA FROM TIFF FILES

%READ HEADER OF TIF FILE
filename = sprintf('%s%s%s',rawdata_folder',matchingFiles{i}(1:end-4),'.tif');
SIimage = tiffMap(filename);
Timestamps = SIimage.timestamps;
frame_rate = SIimage.SI.hRoiManager.scanFrameRate;
FOV_position = SIimage.SI.hMotors.motorPosition;
Zoom = SIimage.SI.hRoiManager.scanZoomFactor;

