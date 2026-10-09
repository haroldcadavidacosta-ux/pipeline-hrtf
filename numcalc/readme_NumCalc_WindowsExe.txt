Warning, compiled Windows binaries MAY BE OBSOLTE! (read below)

This is NumCalc.exe already compiled for Windows 10+ 64bit out of the latest cross-platform source:
https://github.com/Any2HRTF/Mesh2HRTF/tree/develop/mesh2hrtf/NumCalc/src

In addition "- run_NumCalc_instance.bat" file is included to execute the NumCalc.exe one instance at a time. (This is a backup method. Normally use "NumCalcManager.py" to run NumCalc.exe on a complete project)

The NumCalc.exe relies on the included 3 DLL files copied out of the msys2 folder: \msys64\mingw64\bin\ . These .dll files can be updated along with the latest msys2 version that was used to compile NumCalc.exe.



-------------------------------------------------------------------------
Versions:

2022-08-26 version was compiled on “MSYS MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates) includes updated .dll files.

2022-06-21 version was compiled on “MSYS MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates) includes updated .dll files. This specific version is from the /add_numcalcmanager/ branch!
This version adds "RAM estimates" necessary for the latest version of "numcalc_manager"

2022-05-02 version was compiled on “MSYS MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates) includes updated .dll files.

2022-03-21 version was compiled on “MSYS MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates) includes updated .dll files.

2022-02-10 version was compiled on “MSYS MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates) includes updated .dll files.

2022-01-18 version was compiled on “MSYS MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates) includes updated .dll files.

2021-08-06 version was compiled on “MSYS MinGW 64-bit” from the https://www.msys2.org (using the latest pip updates based on msys2-x86_64-20210725.exe installer)



These Windows binaries can be downloaded from:   
https://sourceforge.net/p/mesh2hrtf-tools/code/ci/master/tree/NumCalc_WindowsExe/

Compilation tutorial:
https://sourceforge.net/p/mesh2hrtf/wiki/Installation_2/#compiling-numcalc-on-windows-using-msys2

NOTE: Check that the NumCalc.exe is commited (modified) After the latest changes to the Source. Because some Mesh2HRTF developers only use Linux or Mac, the compiled Windows binaries MAY BE OBSOLTE.
If the compiled NumCalc.exe is missing important NumCalc source commits, then it is recommended to compile a new NumCalc.exe from the latest NumCalc source (see tutorials, it is quite easy).




-------------------------------------------------------------------------
NumCalc is licensed as part of the Mesh2HRTF project. 
https://sourceforge.net/p/mesh2hrtf
Mesh2HRTF is licensed under the GNU Lesser General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

-------------------------------------------------------------------------
msys2 license for the included DLL files only:   	
BSD 3-Clause "New" or "Revised" License
https://www.msys2.org