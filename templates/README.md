# **Neurodata Without Borders (NWB) back-end conversion scripts**

***Scripts*** are useful in converting data from prorpritary formats into NWB format.  Scripts are expected to be used as back-end to U19 data sharing portals: ***usarhythms.ucsd.edu, highandlow.dk.ucsd.edu***

Currently supported experimental data is:
1. Extracellular electrophysiology (Intan -> NWB data conversion)
    + See [README-ephys.md](README-ephys.md) for detailed information
2. Widefield Imaging (Matlab & python)
    + See [README-widefield.md](README-widefield.md) for detailed information
3. 2-Photon Imaging (terminal)
   + See [README-2photon.md](README-2photon.md) for detailed information
4. Behavioral (Matlab or python)
    + See [README-behavior.md](README-behavior.md) for detailed information
5. fMRI (terminal)
   + See [README-mri.md](README-mri.md) for detailed information

## Steps for running python code (manual - terminal) -> send to data portal:

    1. Activate python virtual environment with required modules (nwb on my computer) *see requirements.txt for installed modules
    2. Download and complete Excel sheet that most closely correponds to experiment
    3. Run with 'python share.py' and add terminal arguments as needed

## Steps for running python (manual - terminal) -> just conversion:

    1. Activate python virtual environment with required modules (nwb on my computer) *see requirements.txt for installed modules
    2. Download and complete Excel sheet that most closely correponds to experiment
    3. Run with 'python prep.py' and add terminal arguments as needed

## Steps for running python (manual - Jupyter Notebook):

    1. Activate python virtual environment with required modules (nwb on my computer) *see requirements.txt for installed modules
    2. Open jupyter notebook corresponding to experiment type
    3. Edit constants (file paths at top file) and run

Note: You will need input.xlsx for electrophysiology experiments (sample coming) for inclusion of raw data

## Steps for Matlab (Widefield & Behavioral) -> just conversion:

    1. Install MatNWB as Matlab Add-On (Add-Ons button on top ribbon, search for 'nwb'; and click 'Add' button)
    2. Install Image Processing toolbox Add-On (Add-Ons button on top ribbon, search for 'Image Processing Toolbox'; and click 'Add' button)

## Features

---

- Conversion for Intan format to NWB format (ePhys)
- Ability to add tif image stacks to NWB files (Widefield, Behavioral)
- Integration with back-end relational database (in progress), NoSQL database (in progress)
- Ability to aggregate NWB containers (for uploading to NIH-approved respositories)

## Python Installation

---

1. create virtual environment in home directory (e.g. 'C:/Users/Duane/')
`python -m venv nwb`
2. Activate virtual environment
`C:/Users/Duane/nwb/Scripts/activate.ps1`
3. Install required modules
`pip install -r requirements.txt`

## Contribute

---

[Issue Tracker] (https://github.com/ActiveBrainAtlas2/nwb/issues)

[Source Code] (https://github.com/ActiveBrainAtlas2/nwb)

## Support

---

If you are having issues, please let me know.
Duane Rinehart
drinehart[at]ucsd.edu

## License

---
The project is licensed under the [MIT license](https://mit-license.org/).

---
Last update: 9-JUL-2024