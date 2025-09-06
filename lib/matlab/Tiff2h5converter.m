appFile = "Tiff2h5converter.m"
buildResults = compiler.build.standaloneApplication(appFile);
here is Tiff2h5converter.m that does the trick:
function tiff2h5(filestr)
files =  dir(strcat('*',filestr,'*','\*\display_and_comments.txt'));
for i = 1:size(files,1)
  cd(files(i).folder);
  cd ..\
  checkfile = dir("*_raw.h5");
  if size(checkfile,1) > 0
      continue
  end
[~,currentdir,~]=fileparts(pwd);
im_folder=dir('**\img_000002000_Default_000.tif');
im_size = single(size(readTiff(fullfile(im_folder.folder,im_folder.name))));
im_folder=im_folder.folder;
a = dir([im_folder '\*.tif']);
num_im = numel(a)-1;
h5create([currentdir,'_raw.h5'],'/im_size',[size(im_size,1), size(im_size,2)],'Datatype','single');
h5write([currentdir,'_raw.h5'],'/im_size', im_size, [1 1],[size(im_size,1), size(im_size,2)]);
warning('off','all');
%im_data = zeros(num_im,im_size(1)*im_size(2));
tic
for iter_im = 1 : num_im
    %tmp_im_id = im_sec_list(iter_im);
    if mod(iter_im, 100) == 0
        %fprintf('Reading section %d\n', tmp_im_id);
        fprintf(sprintf('img_%09d_Default_000.tif\n',iter_im));%for micro-manager
        %fprintf(sprintf('F_PV%04d.tiff\n',tmp_im_id));%for adaptor
        % We could do chunk processing here if resources are limited
        % h5write([currentdir,'_raw.h5'],'/im_data', im_data, [iter_im-999 1],[size(im_data,1), size(im_data,2)]);
        % clear im_data
    end
    tmp_fn = fullfile(im_folder, sprintf('img_%09d_Default_000.tif',iter_im)); %for micro-manager
    %tmp_fn = fullfile(im_folder, sprintf('F_PV%04d.tiff', tmp_im_id)); % for adaptor
 
    if isfile(tmp_fn)
        im_data(iter_im,:) = reshape(readTiff(tmp_fn),1,[]);
    else
         fprintf('The file does not exist. %s\n', tmp_fn);
     end
end
toc
warning('on','all');
h5create([currentdir,'_raw.h5'],'/im_data',[size(im_data,1), size(im_data,2)],'Datatype','uint16','ChunkSize',[50 80],'Deflate',9);
h5write([currentdir,'_raw.h5'],'/im_data', im_data, [1 1],[size(im_data,1), size(im_data,2)]);
clear im_data
end
end
