Warning, compiled Windows binaries MAY BE OBSOLTE! (read below)

This is "hrtf_mesh_grading.exe" already compiled for Windows 10+ out of the latest cross-platform source:
https://github.com/cg-tub/hrtf_mesh_grading/

Extra files to use:
> "- run_hrtf_mesh_grading.bat" file provides double-click access to run hrtf_mesh_grading.exe. make sure the input file is called "3Dmesh_orig.stl" (then no changes to the .bat file are needed).

> "- view <something>.bat" files open 3D view of the input and output meshes using identical code as the hrtf_mesh_grading.exe 
(useful for debugging ear positions or corrupt input mesh data).

The hrtf_mesh_grading.exe relies on the included 3 DLL files copied out of the msys2 folder: \msys64\mingw64\bin\ .
 These .dll files can be updated along with the latest msys2 version that was used to compile hrtf_mesh_grading.exe.


-------------------------------------------------------------------------
Versions:

2022-02-12 first Windows version compiled on latest available “mingw32" (32-bit) from the https://osdn.net/projects/mingw/ .

2022-02-12b version was compiled on “MSYS2 MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates) includes updated .dll files.

2022-04-17 updated .bat files to use .stl file on input and changed the default grading settings for more robustness



These Windows binaries can be downloaded from:   
https://sourceforge.net/p/mesh2hrtf-tools/code/ci/master/tree/hrtf_mesh_grading_WindowsExe/

Compilation tutorial:
https://sourceforge.net/p/mesh2hrtf-tools/wiki/Compiling_hrtf_mesh_grading_on_Windows/

NOTE: Check that the hrtf_mesh_grading.exe is commited (modified) After the latest changes to the Source. 
Because the developers only use Linux or Mac, the compiled Windows binaries MAY BE OBSOLTE.
If the compiled hrtf_mesh_grading.exe is missing important source commits, then it is recommended 
to compile a new hrtf_mesh_grading.exe from the latest source (see tutorials).


-------------------------------------------------------------------------
If you use this algorithm please cite the paper:

T. Palm, S. Koch, F. Brinkmann, and M. Alexa, “Curvature-adaptive mesh grading for numerical approximation of head-related transfer functions,” DAGA 2021, Vienna, Austria, pp. 1111–1114.




-------------------------------------------------------------------------

hrtf_mesh_grading is licensed under MIT License. 
see the complete license text next to the source files:
https://github.com/cg-tub/hrtf_mesh_grading/blob/main/LICENSE
-------------------------------------------------------------------------
msys2 license for the included DLL files only:   	
BSD 3-Clause "New" or "Revised" License
https://www.msys2.org
