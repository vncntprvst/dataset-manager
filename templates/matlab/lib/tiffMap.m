classdef tiffMap<handle
    properties
        t;
        fname;
        framesize;
        numframes;
        timestamps;
        SI;
        chidx;
    end
    
    methods
        %Constructor
        function obj = tiffMap(varargin)
            if nargin < 1
                obj.fname = '';
                obj.t = [];
                obj.framesize = [];
                obj.numframes = 0;
                obj.timestamps = [];
                obj.SI = [];
                obj.chidx = [];
            else
                fname = varargin{1};
                obj.fname = fname;
                obj.t = Tiff(fname,'r+');
                
                headerText = obj.t.getTag('Software');
                header = textscan(headerText,'%s','Delimiter','\n');
                header = header{1};
                for i = 1:length(header)
                    if strncmp(header{i},'SI.',3)
                        eval(['obj.' header{i} ';']);
                    end
                end

                obj.framesize(1) = obj.t.getTag('ImageLength');
                obj.framesize(2) = obj.t.getTag('ImageWidth');
                obj.framesize(3) = length(obj.SI.hChannels.channelSave);
                if obj.SI.hFastZ.enable
                    %{
                    try
                        numslices = obj.SI.hStackManager.slicesPerAcq;
                    catch
                        numslices = max(obj.SI.hStackManager.numSlices,numel(obj.SI.hStackManager.zs));
                    end
                    %}
                    numslices = obj.SI.hFastZ.numFramesPerVolume;
                    obj.numframes = obj.SI.hFastZ.numVolumes*numslices;
                else
                    obj.numframes = obj.SI.hStackManager.framesPerSlice*obj.SI.hStackManager.numSlices;
                end
                obj.timestamps = (0:obj.numframes-1)./obj.SI.hRoiManager.scanFrameRate;
                for i = 1:obj.framesize(3)
                    obj.chidx(obj.SI.hChannels.channelSave(i)) = i;
                end
            end
        end
        
        function validate(obj)
            obj.t.setDirectory(1);
            nfr = 1;
            d = obj.parseDescription(obj.t.getTag('ImageDescription'));
            time(1) = str2double(d('frameTimestamps_sec'));
            
            while ~obj.t.lastDirectory()
                obj.t.nextDirectory();
                nfr = nfr + 1;
                d = obj.parseDescription(obj.t.getTag('ImageDescription'));
                time(nfr) = str2double(d('frameTimestamps_sec'));
            end
            
            obj.numframes = floor(nfr/obj.framesize(3));
            time = reshape(time,obj.framesize(3),nfr);
            obj.timestamps = mean(time,1);
            
        end
        
        %Overloaded index reading.
        function b = subsref(obj,S)
            if strcmp(S(1).type,'()') && length(S) < 2
                switch length(S(1).subs)
                    case 1
                        if ischar(S(1).subs{1})
                            b = obj.readcontiguousframes(obj.SI.hChannels.channelSave,1,obj.numframes);
                        else
                            b = obj.readframes(obj.SI.hChannels.channelSave,S(1).subs{1});
                        end
                    case 2
                        if ischar(S(1).subs{1})
                            if ischar(S(1).subs{2})
                                b = obj.readcontiguousframes(1:obj.framesize(3),1,obj.numframes);
                            else
                                b = obj.readframes(1:obj.framesize(3),S(1).subs{2});
                            end
                        else
                            if ischar(S(1).subs{2})
                                b = obj.readcontiguousframes(S(1).subs{1},1,obj.numframes);
                            else
                                b = obj.readframes(S(1).subs{1},S(1).subs{2});
                            end
                        end
                    otherwise
                        b = -1;
                end
            else
                b = builtin('subsref',obj,S);
            end
        end
        
        %Overloaded save to handle tiff.
        function s = saveobj(obj)
            s.fname = obj.fname;
            s.framesize = obj.framesize;
            s.numframes = obj.numframes;
            s.timestamps = obj.timestamps;
            s.SI = obj.SI;
            s.chidx = obj.chidx;
        end
        
        function desc = parseDescription(obj,description)
            pattern = '[a-zA-Z_]+ = [\d.]+';
            x = regexp(description,pattern,'match');
            desc = containers.Map;
            for i = 1:length(x)-1
                y = strsplit(x{i},' = ');
                desc(y{1}) = y{2};
            end
        end
        
        function fr = readframes(obj,channels,idx)
            cont = diff(idx);
            if sum(bsxfun(@eq,cont,1)) == length(idx) - 1
                fr = readcontiguousframes(obj,channels,idx(1),length(idx));
            else    
                channels = obj.chidx(channels);
                if ~isempty(find(channels == 0,1))
                    chanexcept = MException('Index:InvalidChannel','Invalid channels.');
                    throw(chanexcept);
                end
                fr = zeros(obj.framesize(1),obj.framesize(2),length(channels),length(idx),'int16');
                for i = 1:length(idx)
                    obj.t.setDirectory(obj.framesize(3)*(idx(i)-1)+1);
                    curridx = 1;
                    if ismember(1,channels)
                        fr(:,:,1,i) = obj.t.read();
                        curridx = curridx + 1;
                    end
                    for c = 2:obj.framesize(3)
                        obj.t.nextDirectory();
                        if ismember(c,channels)
                            fr(:,:,curridx,i) = obj.t.read();
                            curridx = curridx + 1;
                        end
                    end
                end
            end
        end
        
        %Here we can iterate using nextDirectory rather than setDirectory
        %(is this faster?)
        function b = readcontiguousframes(obj,channels,start,nfr)
            channels = obj.chidx(channels);
            if ~isempty(find(channels == 0,1))
                chanexcept = MException('Index:InvalidChannel','Invalid channels.');
                throw(chanexcept);
            end
            b = zeros(obj.framesize(1),obj.framesize(2),length(channels),nfr,'int16');
            obj.t.setDirectory(obj.framesize(3)*(start-1)+1);
            for i = 1:nfr-1
                curridx = 1;
                for c = 1:obj.framesize(3)
                    if ismember(c,channels)
                        b(:,:,curridx,i) = obj.t.read();
                        curridx = curridx+1;
                    end
                    try
                        obj.t.nextDirectory();
                    catch
                        disp('Invalid frame numbers.');
                        b = b(:,:,:,1:i);
                        return;
                    end
                end
            end
            
            curridx = 1;
            for c = 1:obj.framesize(3) - 1
                if ismember(c,channels)
                    b(:,:,curridx,end) = obj.t.read();
                    curridx = curridx+1;
                end
                obj.t.nextDirectory();
            end
            if ismember(obj.framesize(3),channels)
                b(:,:,end,end) = obj.t.read();
            end
        end
	end
    
    methods(Static)
        %Overloaded load for tiff.
        function obj = loadobj(s)
            obj = tiffMap();
            obj.framesize = s.framesize;
            obj.numframes = s.numframes;
            obj.timestamps = s.timestamps;
            obj.chidx = s.chidx;
            obj.SI = s.SI;
            
            obj.fname = s.fname;
            if exist(obj.fname,'file') == 2
                obj.t = Tiff(obj.fname,'r+');
            else
                [~,n,e] = fileparts(obj.fname);
                lname = fullfile(cd,[n,e]);
                if exist(lname,'file') == 2
                    obj.t = Tiff(lname,'r+');
                    obj.fname = lname;
                else
                    obj.t = -1;
                    obj.fname = '';
                    warning('No tiff file found to associate with map. Please move the tiff file to the same directory as this map file.');
                end
            end
        end 
    end
end
        
    