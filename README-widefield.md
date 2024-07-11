# **Widefield Imaging: 2-photon processing**

## Steps for running (manual):

    1. Experimenter should download [templates/input_widefield_2P.xlsx](templates/input_widefield_2P.xlsx), complete spreadsheet with relevant information 
        about experiment
        * File locations for image stacks should be entered in 'src_folder_directory' column (relative to location of Excel file or using absolute path)

    2. For each sequence of image files (image_recordings), corresponding to a row in input_widefield_2P.xlsx file, a separate file should be created to reference each recording.
        i.e., [templates/widefield_recordings.xlsx](templates/widefield_recordings.xlsx) should be populated 
          with file locations of each tiff file recording that correspond to a specific experimental session_id.  This file location 
          should be referenced in 'src_folder_directory' column of input_widefield_2P.xlsx

        Note: [Matlab/Widefield_2Photon_nwb.m](Matlab/Widefield_2Photon_nwb.m) (Matlab script) will read image 
          files from this Excel sheet. 

    3. Once input_widefield_2P.xlsx and image_recordings are in place, user will need to add 
        locations of these input files (paths) and paths for output (where NWB files will be
          stored - with enough storage). See 'optional arguments' below for defining output folder 

    4. Copy entire matlab directory, including subfolders, into same location as primary Excel file, input_widefield_2P.xlsx.
    5. Modify Widefield_2Photon_nwb.m [% APP CONSTANTS (DEFAULT) SECTION] for your actual storage locations
        primary_experiments_table = Location of primary input (.xlsx) file (relative to Matlab file)
        output_path = Location where NWB files will be written
        summary_data_path = Location where Figure plotting data is stored

## Steps for validating NWB files (manual):

    1. Use [nwb_utils.ipynb](nwb_utils.ipynb) (Jupyter Notebook) to validate NWB files
        after processing.  See 'MANUAL EXAMINE CONTENTS OF NWB FILE' in header block

## Files

---


- Widefield_2Photon_nwb.m (main file for collecting/processing experimental data and figures)
- templates/input_widefield_2P.xlsx  (Contains meta-data about experiment and locations of subject id recording locations)
  * Note: This file is parsed by Widefield_2Photon_nwb.m
- templates/recordings.xlsx (Contains meta-data and locations of tif recordings)
  * Note: This file is parsed by Widefield_2Photon_nwb.m