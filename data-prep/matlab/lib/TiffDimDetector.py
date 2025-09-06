#!/usr/bin/env python
# coding: utf-8

# CREATED: 7-DEC-2022
# LAST EDIT: 16-JUL-2024
# AUTHORS: DUANE RINEHART, MBA (drinehart@ucsd.edu), Jacob Duckworth (jaduckwo@ucsd.edu)

# Read tif file with python-bioformats

from pathlib import Path, PurePath, PureWindowsPath
from tifffile import imread, TiffFile
import sys

#################################################################
input_path = Path(sys.argv[1])
input_path = str(input_path).replace("**"," ")
#################################################################
# print(f"DEBUG: argumentcaptured:{input_path}")
print(input_path)

tif = TiffFile(input_path) #Commented out

print(len(tif.pages))
series = tif.series[0];
print(series.shape)

numims = len(tif.pages)


# #################################################################
# def getims(r1,r2,r3):
# 
#     input_path = Path(sys.argv[1])
#     input_path = str(input_path).replace("**"," ")
# 
#     tif = TiffFile(input_path)
# #################################################################
# #READ IMAGE STACK WITH tifffile
# # image = imread(input_path)
# # print(image.shape)
# 
#     #key tells it to read from image r1 to r2 in steps of r3. Values for r1,r2,r3 are set in MATLAB
#     images = imread(input_path, key=range(int(r1), int(r2), int(r3)));
#     print(range(r1, r2, r3))
#     print(images.dtype)
# 
#     test = images;
#     return test
# 
# imsout = getims(r1,r2,r3);
# 
# #print(len(tif.pages))
# #series = tif.series[0];
# #print(series.shape)
# #return len(tif.pages)
# #test = len(tif.pages)