# **Extracellular electrophysiology processing**

## Steps for running (manual):

    1. Experimenter should download [templates/input_ephys.xlsx](templates/input_ephys.xlsx), complete spreadsheet with relevant information 
        about experiment
        * File locations for image stacks should be entered in 'src_folder_directory' column (relative to location of Excel file or using absolute path)
    2. Electrode measurements e.g. Intan should be provided as separate Excel workbook
        i.e., [templates/electrode_mappings.xlsx](templates/electrode_mappings.xlsx) should be populated 
          with correct mappings for each experimental session_id.  This file location 
          should be referenced in 'electrode_recordings' column of input_ephys.xlsx

        Note: [nwb_utils.ipynb](nwb_utils.ipynb) (Jupyter Notebook) has
          code to extract mappings from existing Intan output files or sequence of 
          mappings in Excel sheet. See 'PRE-PROCESS ELECTRODE MAPPINGS' in header block
    3. Once input_ephys.xlsx and electrode mappings are in place, user will need to add 
        locations of these input files (paths) and paths for output (where NWB files will be
          stored - with enough storage). See 'optional arguments' below for defining output folder 
    4. Download prep.py into same folder as Excel file.
      Note: prep.py is terminal script and will require arguments to work correctly
      N.B. required argument is absolute or relative path of Excel file (-i)
      * optional argument: output folder (-o)
      * optional argument: experiment modality (-exp), where 1=ephys,2=widefield,3=2photon,4=behavior;5=fMRI
      * optional argument: researcher (-researcher) - string in quotes
      * optional argument: institution (-institution) - string in quotes
      
      example terminal command: 
      python .\prep.py -i E:\temp\ephys-youngbin\input\input_ephys.xlsx -o E:\temp\output -exp 2 -researcher 'Pantong' -institution 'UC San Diego'

      Excel file has experimenters, institution headers however command line arguments will take priority
      If output folder is not defined, script will create folder in current working directory

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
- templates/input_ephys.xlsx (Contains meta-data about experiment and locations of electrode mappings)
  * Note: This file is parsed by ephys_process.ipynb
- templates/electrode_mappings.xlsx (Contains locations of electrode mappings to board)
  * Note: This file is parsed by ephys_process.ipynb