# **widefield processing**

## Steps for running (manual):

    1. Experimenter should download [Matlab/input_widefield_2P.xlsx](Matlab/input_widefield_2P.xlsx), complete spreadsheet with relevant information about each experiment (file in Matlab folder)
        * File locations for images should be entered in 'src_folder_directory' column
    2. Experimenter should download [Matlab/Widefield_2Photon_nwb.m](Matlab/Widefield_2Photon_nwb.m), update sections with the desired entries to the nwb file (file in Matlab folder)
    3. Download the matnwb package [here](https://www.mathworks.com/matlabcentral/fileexchange/67741-neurodatawithoutborders-matnwb) or through the Matlab Add-On Explorer. 
    4. Update the Widefield_2Photon_nwb.m file as needed
        * input_path and output_path
        * subj_* information
        * dynamic table; general purpose holder for scatter plot or histogram data. Documentation [here]https://neurodatawithoutborders.github.io/matnwb/tutorials/html/dynamic_tables.html.
        * time series; holder for time-series data. Time points or rate and starting time are required. For constant-rate data nwb prefers single start time and sample rate. Documentation [here](https://neurodatawithoutborders.github.io/matnwb/doc/+types/+core/TimeSeries.html).
        * other data types (images etc.) can be added by following the documentation [here](https://neurodatawithoutborders.github.io/matnwb/doc/NwbFile.html).
    5. Run Widefield_2Photon_nwb.m in Matlab to create nwb files.

## Steps for validating NWB files (manual)

    1. (WIP) Search share.py code for 'VALIDATE .NWB FILE' for how to do this.
        * NWB Inspector [https://github.com/NeurodataWithoutBorders/nwbinspector](https://github.com/NeurodataWithoutBorders/nwbinspector) is used for validation of output files
    2. In PowerShell, open python virtual environment: "python -m venv nwb"
    3. Run nwbinspector on your nwb file: "nwbinspector output_path\Figure1.nwb" where "Figure1.nwb" is your nwb file name. 
    4. Correct all critical issues by editing and re-running Widefield_2Photon_nwb.m

## Required Files

---

- Matlab/input_widefield_2P.xlsx (Contains meta-data about experiment and locations of image stacks)
- Matlab/Widefield_2Photon_nwb.m 