# **Extracellular electrophysiology processing**

## Steps for running (manual):

    1. Experimenter should complete input.xlsx spreadsheet with relevant information 
        about experiment (file in templates folder)
    2. Electrode measurements e.g. Intan should be provided as separate Excel workbook
        i.e., electrode_mappings.xlsx (file in templates folder) should be populated 
          with correct mappings for each experimental session_id.  This file location 
          should be referenced in 'electrode_recordings' column of input.xlsx

        Note: [nwb_utils.ipynb](nwb_utils.ipynb) (Jupyter Notebook) has
          code to extract mappings from existing Intan output files or sequence of 
          mappings in Excel sheet. See 'PRE-PROCESS ELECTRODE MAPPINGS' in header block
    3. Once input.xlsx and electrode mappings are in place, user will need to add 
        locations of these input files (paths) and paths for output (where NWB files will be
          stored - with enough storage). See 'APP CONSTANTS' in header block of
          [ephys_process.ipynb](ephys_process.ipynb)


## Steps for validating NWB files (manual):

    1. Use [nwb_utils.ipynb](nwb_utils.ipynb) (Jupyter Notebook) to validate NWB files
        after processing.  See 'MANUAL EXAMINE CONTENTS OF NWB FILE' in header block

## Files

---

- ephys_process.ipynb (Main Notebook for reading and processing ephys files -> reads input.xlsx and electrode_mappings.xlsx; generates NWB output files)
    - For Intan format, uses ConvertIntanToNWB.py and WriteNWB.py 
- nwb_utils.ipynb 
    - code to generate electrode_mappings.xlsx file from source files
    - code to validate NWB files after generation