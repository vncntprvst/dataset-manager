# **widefield processing**

## Steps for running (manual):

    1. Experimenter should download [Matlab/input_widefield_2P.xlsx](Matlab/input_widefield_2P.xlsx), complete spreadsheet with relevant information about each experiment (file in Matlab folder)
        * File locations for images should be entered in 'src_folder_directory' column
    2. Experimenter should download [Matlab/Widefield_2Photon_nwb.m](Matlab/Widefield_2Photon_nwb.m), update sections with the desired entries to the nwb file (file in Matlab folder)
    3. Download the matnwb package [here](https://www.mathworks.com/matlabcentral/fileexchange/67741-neurodatawithoutborders-matnwb) or through the Matlab Add-On Explorer. 
    4. Update the Widefield_2Photon_nwb.m file as needed
        * input_path and output_path
        * subj_* information
        * each section for nwb file entries, now labeled as Figure_x
    5. Run Widefield_2Photon_nwb.m in Matlab to create nwb files.

## Steps for validating NWB files (manual)

    1. (WIP) Search share.py code for 'VALIDATE .NWB FILE' for how to do this.
        * NWB Inspector [https://github.com/NeurodataWithoutBorders/nwbinspector](https://github.com/NeurodataWithoutBorders/nwbinspector) is used for validation of output files

## Required Files

---

- data-sharing/share.py (Main python script for running conversion from image tif image stacks to NWB format)
  * Note: Default output files stored in 'output' folder (script creates if it does not exist)  
- templates/input_2photon.xlsx (Contains meta-data about experiment and locations of image stacks)
  * Note: This file is parsed by share.py