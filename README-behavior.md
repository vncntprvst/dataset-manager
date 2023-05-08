# **Behavior processing**

## Steps for running (manual):

    1. Experimenter should download [templates/input_behavior.xlsx](templates/input_behavior.xlsx), complete spreadsheet with relevant information 
        about experiment
        * File locations for image stacks should be entered in 'src_folder_directory' column (relative to location of Excel file or using absolute path)
    2. Once input_behavior.xlsx is in place, user will need to add 
        locations of these input files (paths) and paths for output (where NWB files will be
          stored - with enough storage). See 'optional arguments' below for defining output folder
    3. Download prep.py into same folder as Excel file.
      Note: prep.py is terminal script and will require arguments to work correctly
      N.B. required argument is absolute or relative path of Excel file (-i)
      * optional argument: output folder (-o)
      * optional argument: experiment modality (-exp), where 1=ephys,2=widefield,3=2photon,4=behavior;5=fMRI
      * optional argument: researcher (-researcher) - string in quotes
      * optional argument: institution (-institution) - string in quotes
      
      example terminal command: 
      python data-sharing/prep.py -i /net/birdstore/Songmao/CURBIO_SL_DK/input_behavior_linux2_full.xlsx -o /net/birdstore/Songmao/output -exp 4

      Excel file has experimenters, institution headers however command line arguments will take priority
      If output folder is not defined, script will create folder in current working directory

## Steps for validating NWB files (manual):

    1. Use [nwb_utils.ipynb](nwb_utils.ipynb) (Jupyter Notebook) to validate NWB files
        after processing.  See 'MANUAL EXAMINE CONTENTS OF NWB FILE' in header block

## Files

---

- prep.py (Main script to read input Excel spreadsheet, to process behavior files (ex. Matlab, Video, other); and to generate NWB output files)
- nwb_utils.ipynb
    - code to validate NWB files after generation
- templates/input_behavior.xlsx (Contains meta-data about experiment and other file locations)
  * Note: This file is parsed by prep.py

## Errata Notes

- Current template file for behavior (as of 8-MAY-2023) used for processing the following types of files:
.avi (external)
.csv (external)(timeseries - location "torso")
.mat (geometry [ellipse] - comment to image series)
.xlsx(timeseries - sensor data: ndarray)
.mat (timeseries - data [36data]: ndarray)
.mat (other meta-data [LCmat]: ndarray)
.csv (processing ref) - matrix
.mat (analysis ref) - matrix
.csv (stimulus_notes_file) - string
.csv (notes) - string