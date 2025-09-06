# **2 photon processing**

## Steps for running (manual):

    1. Experimenter should download [templates/input_2photon.xlsx](templates/input_2photon.xlsx), complete spreadsheet with relevant information 
        about experiment (file in templates folder)
        * File locations for image stacks should be entered in 'src_folder_directory' column
    2. Save input_2photon.xlsx in parent folder of data folders (as defined in #2 above) and copy [data-sharing/share.py](data-sharing/share.py) to same root folder
    3. Activate python virtual environment
        * (Windows) Run 'activate.ps1' in Scripts folder of virtual environment
        * (Linux/Mac) Run 'source activate' in bin folder of virtual environment
    4. Run python share.py -i input_2photon.xlsx
        * Note: The arguments passed to share.py change how it runs and where to find input (Excel) file
  
    

## Steps for validating NWB files (manual)

    1. (WIP) Search share.py code for 'VALIDATE .NWB FILE' for how to do this.
        * NWB Inspector [https://github.com/NeurodataWithoutBorders/nwbinspector](https://github.com/NeurodataWithoutBorders/nwbinspector) is used for validation of output files

## Required Files

---

- data-sharing/share.py (Main python script for running conversion from image tif image stacks to NWB format)
  * Note: Default output files stored in 'output' folder (script creates if it does not exist)  
- templates/input_2photon.xlsx (Contains meta-data about experiment and locations of image stacks)
  * Note: This file is parsed by share.py