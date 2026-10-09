# Verificación del código fuente de NumCalc

Fecha: 2026-10-04. Cada afirmación lleva archivo, línea y un fragmento literal del código. Lo que no se encontró en el
código está en la lista final y no se completa con documentación ni con lo habitual en otros solvers. La
documentación del repositorio (`docs/`) no menciona el resolvedor, Burton-Miller, la tolerancia, el tipo de elemento
ni la convención temporal (búsqueda sin resultados), así que todo lo de abajo sale del código.

## Paso 0: correspondencia de versiones

**El fuente local es posterior al binario.**

| Qué | Evidencia |
|---|---|
| Fuente local | `Mesh2HRTF-1.3.0/VERSION`: `1.3.0`. `HISTORY.rst`, línea 4: `v1.3.0 (20 March 2026)` |
| Binario | `NumCalc_WindowsExe/readme.txt`: `2022-08-26 version was compiled on "MSYS MinGW 64-bit"`, compilado desde `https://github.com/Any2HRTF/Mesh2HRTF/tree/develop/mesh2hrtf/NumCalc/src`. SHA-256 del `.exe`: `3ab7d18ee6c0963b…` (654 681 bytes) |
| Fuente más cercano al binario | Historial de GitHub de `mesh2hrtf/NumCalc/src`: el último commit anterior al 2022-08-26 es `001351d7e19b6940ad33b9cccd5c285947c48e55` (2022-08-18, «removed the warning…»); el siguiente es `9273e03c7b` (2022-11-17, LAPACK). Ese fuente se descargó y se usó para la columna «2022» |
| Cambios de NumCalc entre ambos | 24 commits. Los que tocan lo verificado aquí: opción `-adapt_fmmlength` (2026-02-05), `-check_normals` (2024-07-19), resolvedor directo LAPACK opcional (2022-11-17, solo si se compila con `USE_LAPACK`), corrección de `estimate_ram` (2025-06-12). El resolvedor CGS, la tolerancia, el máximo de iteraciones, Burton-Miller, la función de Green y el criterio de FMM no cambian (diff de los dos fuentes: en `NC_CommonFunctions.cpp` solo cambian espacios en blanco) |

**Supuesto declarado:** que el binario se compiló desde `001351d7e1`. Es muy probable (es el estado de `develop` entre el
2022-08-18 y el 2022-11-17, y el binario se compiló en ese intervalo), pero no se puede demostrar: el readme dice que
una versión anterior (2022-06-21) salió de otra rama. Por eso cada fila distingue:

- **Binario: verificado** — hay evidencia en el propio binario: la cadena está en el `.exe` o aparece en una salida
  real (`datos/experimentos/barrido_e/fase2/e_1/NumCalc/source_1/NC78-78.out`, 24 kHz con -e 1, que divergió).
- **Binario: verificado por comportamiento** — no hay cadena que buscar (es una constante numérica), pero el
  comportamiento medido del binario la acota o la confirma: distribución de lo que imprime o una transición medida.
  Es distinto de «verificado por cadena en el `.exe`».
- **Binario: probable** — el mismo código está en el fuente de 2022, sin evidencia directa en el binario.
- **Solo fuente** — no está en el fuente de 2022 ni en el binario.

Rutas: `src/` = `Mesh2HRTF-1.3.0/mesh2hrtf/NumCalc/src/` (v1.3.0). «2022:» = misma ruta en el commit `001351d7e1`.

## Grupo 1: solución del sistema

| # | Afirmación verificada | v1.3.0: archivo:línea | Fragmento literal | 2022: línea | Binario 2022-08-26 |
|---|---|---|---|---|---|
| 1.1 | El método iterativo es **CGS** (Conjugate Gradient Squared), según A. Meister p. 168 | `src/NC_CommonFunctions.cpp:1065-1066` | `// CGS solver for the BEM equation system (Andreas Meister, p 168)` / `void NC_IterativeSolverCGS` | 1065-1066 | **Verificado**: la salida real imprime `methodSolver_  = 0: CGS iterative solver` y `CGS solver: number of iterations = 250, relative error = 999523` |
| 1.1b | Solo se admiten CGS (0) y eliminación gaussiana directa (4); con FMM el 4 se cambia a 0 | `src/NC_Input.cpp:272-273`, `290` | `if(methodSolver_ > 0 && methodSolver_ < 4)` … `NC_Error_Exit_1(NCout, "ISOLVER must be 0 or 4!", …)` / `if(methodFMM_ && methodSolver_ == 4) methodSolver_ = 0;` | 265, 283 | Probable |
| 1.1c | El método se elige en NC.inp, «Main Parameters I», noveno valor | `src/NC_Input.cpp:253` | `methodSolver_ = NC_String2Integer(chterms[8]);` | 246 | Probable. Tu NC.inp: `2 28152 14082 0 0 2 1 4 0` → noveno valor 0 = CGS |
| 1.2 | **No es una variante reiniciada.** CGS no tiene parámetro m. El único «reinicio» del código es otro: si el precondicionador ILU parece casi singular (algún componente de A·x0 con norma > 1e8), con FMM se cambia al precondicionador de escalado y se vuelve a empezar | `src/NC_CommonFunctions.cpp:1106-1114` | `if(zV_j[i].norm() > 1.0e8)` … `methodPreconditioner_ = 1;` … `"ILU preconditioning failed, the row scanning method is used!"` … `goto BeginCGS;` | 1106-1114 | Probable (la cadena del aviso no aparece como texto plano en el `.exe`; ver nota 3) |
| 1.3 | Hay precondicionador. Por defecto (`0`) es **ILU** (factorización LU incompleta, A. Meister p. 197) | `src/NC_CommonFunctions.cpp:1080-1088`, `1356` | `case 0: // ILU` → `NC_IncompleteLUDecomposition(NCout);` / `case 1: // row scanning` → `NC_ComputeScalingVector(NCout);` | 1080-1088 | **Verificado**: la salida real imprime `methodPreconditioner_ = 0: incomplete LU-decomposition preconditioner` |
| 1.3b | Se puede desactivar: quinto valor de «Main Parameters II» de NC.inp. Valores: 0 = ILU, 1 = escalado, 2 = ninguno; −1, −2, −3 = ILU con umbral de llenado distinto (`scanningDegreeLU_`) | `src/NC_Input.cpp:298`, `306-320`; `src/NC_CommonFunctions.cpp:1229` | `methodPreconditioner_ = NC_String2Integer(chterms[4]);` / `if(methodPreconditioner_ < -3 \|\| methodPreconditioner_ > 2)` / `case 2: // no preconditioning` | 291, 299-313, 1229 | Probable. Tu NC.inp: `0 0 0 0.0000e+00 0 0 0` → quinto valor 0 = ILU |
| 1.3c | El precondicionador se aplica **por la derecha**: en cada producto matriz-vector se aplica primero al vector y después se multiplica por la matriz | `src/NC_CommonFunctions.cpp:1220-1225` | `// prconditioning` … `case 0: // ILU` → `NC_IncompleteLUForBack(NCout, zmultvect, ztmp);` (y luego el producto con `ztmp`) | 1220-1225 | Probable |
| 1.3d | **Con ILU, además, cada fila de la matriz y del lado derecho se reescala** antes de factorizar (equilibrado por filas), también en ML-FMM | `src/NC_CommonFunctions.cpp:1441-1461` | `case 3: // DMLFMBEM` … `dwk = sqrt((double)(irownea[i + 1] - irownea[i])/dw1);` … `zcoefl[j] *= dwk;` … `smtxlev[ilv].zSmxLv[j] *= dwk;` … `zrhs[i] *= dwk;` | 1441-1461 | Probable |
| 1.4 | **Tolerancia por defecto: 1e-9**, fija en el código. No se lee de NC.inp ni de la línea de comandos | `src/NC_CommonFunctions.cpp:39`, `1162` | `double ErroIterSols = 1.0e-9;` / `if(err_rel < ErroIterSols \|\| j == niter_max_)` | 39, 1162 | **Verificado por comportamiento del binario.** Factor final de los 1484 pasos convergidos con el binario (`datos/experimentos/auditoria/factor_residuo.json`, actualizado el 2026-10-09 con todas las corridas: barrido, -e 1 -y 5, los seis de A, la corrida manual de HUTUBS y la HRTF de producción de A1, 320 pasos; las versiones anteriores, de 721 y 1164 pasos, quedaron en `auditoria/anterior_*_pasos/`): de 5,7e-12 a 9,9924e-10, 91 % entre 1e-10 y 1e-9. Cota inferior, deductiva: el bucle solo sale antes del tope si factor < T, así que T > 9,9924e-10. Cota superior, estadística: ningún paso entre 1e-9 y 1e-6 sobre 1484 (un umbral más alto habría dejado pasos parados en esa ventana). El intervalo (9,9924e-10, ~1e-9] contiene el valor del fuente con un margen del 0,08 %. La cota inferior depende de la estructura del bucle leída en el fuente |
| 1.4b | **El `0.000001` de «Controlparameter II» en NC.inp no es la tolerancia**: es el incremento de paso de la curva de frecuencias | `src/NC_Input.cpp:205-209` | `// Kontrollparameter II` … `numFrequencies_ = NC_String2Integer(chterms[1]);` / `frequencyStepIncrement_ = NC_String2Double(chterms[2]);` / `firstFrequencyStep_ = NC_String2Double(chterms[3]);` | 198-202 | **Verificado**: la salida real imprime `Step increment ..... = 1e-06` |
| 1.4c | **Máximo de iteraciones por defecto: 250.** Se cambia por línea de comandos con `-nitermax`; no se lee de NC.inp | `src/NC_Main.cpp:83`, `173-177` | `int niter_max_ = 250;` / `else if(!strcmp(argv[i],"-nitermax")) {` … `niter_max_ = atoi( argv[i] );` | 75, 162-166 | **Verificado**: `-nitermax` está en el `.exe`, y la frecuencia divergida se detuvo en `number of iterations = 250` |
| 1.4d | El contador impreso es el índice `j` del bucle, que empieza en 0 y llega como máximo a `niter_max_` | `src/NC_CommonFunctions.cpp:1126`, `1178-1179` | `for(j=0; j<=niter_max_; j++)` / `NCout << "\nCGS solver: number of iterations = " << j << ", relative error = " << err_rel << endl;` | 1126, 1178-1179 | Verificado (formato de salida idéntico) |
| 1.5 | **Crítico: el «relative error» impreso NO es ‖b − A·x‖ / ‖b‖.** Es `‖r_j‖ / ‖r_1‖`: la norma 2 del residuo en la iteración j dividida por la del residuo **después de la primera iteración** (`j == 0`), no por la del residuo inicial ni por ‖b‖ | `src/NC_CommonFunctions.cpp:1138-1155` | `dwk1 += zR_j[i].qnorm();` … `if(j == 0) { err_ori = sqrt(dwk1);` … `} else { err_rel = sqrt(dwk1)/err_ori; }` | 1138-1155 | Probable |
| 1.5b | Ese residuo `r_j` es el de la recurrencia de CGS (`r ← r − α·A(u+q)`), no un `b − A·x` recalculado | `src/NC_CommonFunctions.cpp:1124`, `1139-1145` | `zR_j[i] = … = zrhs[i] - zV_j[i];` (solo al inicio) … `zR_j[i] -= zalph*zAUQ_j[i];` | 1124, 1139-1145 | Probable |
| 1.5c | Ese residuo es el del **sistema precondicionado y reescalado**: con ILU (1.3d), `b` y las filas de `A` están multiplicadas por los factores `dwk`, y el operador es `A·M⁻¹` (1.3c). Es decir: residuo = `D·(b − A·x)`, con D la diagonal de factores por fila | Ver 1.3c y 1.3d | (fragmentos de 1.3c y 1.3d) | — | Probable |
| 1.5d | El vector inicial es cero | `src/NC_CommonFunctions.cpp:1096` | `zX_j[j].set(0.0,0.0);` | 1096 | Probable |
| 1.5e | Además, cada 10 iteraciones se escribe en la consola (stdout, no en NC.out) el error relativo y el absoluto | `src/NC_CommonFunctions.cpp:1157-1160` | `cout << j << " " << err_rel << endl;` / `cout << j << " Abs Error:" << sqrt(dwk1) << endl;` | 1157-1160 | Probable |

## Grupo 2: formulación

| # | Afirmación verificada | v1.3.0: archivo:línea | Fragmento literal | 2022: línea | Binario 2022-08-26 |
|---|---|---|---|---|---|
| 2.1 | Burton-Miller: el factor de la derivada normal es **β = i·h/k**, donde h es el factor de tiempo armónico (+1 por defecto, ver 2.2), así que β = **i/k** por defecto. El factor de la ecuación sin derivar es 1 | `src/NC_EquationSystem.cpp:83-85` | `// set the coupling constant` / `Gama3 = 1.0;` / `if(isInternalProblem_) {zBta3.set(0.0, 0.0);} else {zBta3.set(0.0, harmonicTimeFactor_/waveNumbers_);}` | 84-86 | Probable para el valor. Verificado que es problema exterior: la salida real imprime `Exterior domain problem` |
| 2.1b | Se aplica a **todo problema exterior**, sin condición de frecuencia ni de malla; en problemas interiores β = 0. Exterior o interior se fija en NC.inp, «Main Parameters II», tercer valor | `src/NC_EquationSystem.cpp:85`; `src/NC_Input.cpp:296` | (línea 85 de arriba) / `isInternalProblem_ = NC_String2Integer(chterms[2]);` | 86, 289 | Probable. Tu NC.inp: tercer valor 0 = exterior |
| 2.2 | Convención temporal: factor h leído de NC.inp, «Main Parameters IV», tercer valor; cualquier valor distinto de −1 se convierte en +1. Con h = +1 el programa declara **e^{−iωt}** | `src/NC_Input.cpp:332-334`, `1538-1545` | `harmonicTimeFactor_ = NC_String2Double(chterms[2]);` / `if(harmonicTimeFactor_ != -1.0) harmonicTimeFactor_ = 1.0;` / `NCout << "Harmonic time factor = EXP(-i*omega*t)" << endl;` | 325-327, 1486 | **Verificado**: tu NC.inp trae `343 1.1839e+00 1.0 …` y la salida real imprime `Harmonic time factor = EXP(-i*omega*t)` |
| 2.2b | Función de Green en el código: **G = e^{+i·h·k·r} / (4πr)**; con h = +1, exponente **positivo** (e^{+ikr}) | `src/NC_EquationSystem.cpp:1632`, `1705-1710` | `wavruim = harmonicTimeFactor_*waveNumbers_;` / `// compute the kernal functions //exp(ikr)/r/4/pi` / `re1 = wavruim*disfsp;//ikr` / `re2 = wga/PI4/disfsp;` / `zg.set(cos(re1)*re2, sin(re1)*re2);//exp(ikr)/r/4/pi` | 1616, 1689-1694 | Probable |
| 2.3 | **Una incógnita por elemento** (presión o potencial constante por elemento): el sistema tiene una fila por elemento de contorno | `src/NC_Addresses.cpp:178-184` | `// compute the array JELIST (addresses of unknowns of each element in the global system)` … `jelist[i][0] = numRowsOfCoefficientMatrix_++;` | 183 | Probable |
| 2.3b | La condición de contorno nodal se promedia sobre los nodos del elemento | `src/NC_EquationSystem.cpp:149-151` | `for(i=0; i<listNumberNodesPerElement[iel]; i++) Zbvi03 += zbval0[iel][i];` / `Zbvi03 /= (double)listNumberNodesPerElement[iel];` | 150-152 | Probable |
| 2.4 | Cada fila se evalúa en **un solo punto, el centro del elemento** (punto fuente), y la integración con puntos de Gauss se hace solo sobre el elemento de campo. Es la estructura de un método de **colocación**; no se encontró ninguna integración sobre el elemento fuente ni la palabra «Galerkin». El código llama a ese punto «collocation node» en un comentario | `src/NC_EquationSystem.cpp:114-118`, `1679-1710`; `src/NC_PostProcessing.cpp:505` | `// center point and normal vector` … `Sourpoi3[i] = centel[iel][i];` / `for(i=0; i<NDIM; i++) diffsp[i] = crdpoi[i] - Sourpoi3[i];` / `before we looked at the collocation node level = elem midpoint level` | 117-118, 1690 | Probable |
| 2.5 | **El coeficiente C(r) está fijo en 1/2**: el término libre se suma con un factor literal 0,5, sin calcular ángulo sólido | `src/NC_EquationSystem.cpp:218-226` | `// compute of the free terms of the coefficient matrix` … `+= (Admia3*zBta3 - Gama3)*0.5;` / `-= zBta3*(0.5*Tao_);` | 219-227 | Probable |

## Grupo 3: comportamiento observado

| # | Afirmación verificada | v1.3.0: archivo:línea | Fragmento literal | 2022: línea | Binario 2022-08-26 |
|---|---|---|---|---|---|
| 3.1 | Al llegar al máximo de iteraciones el programa **solo escribe un aviso** y sigue | `src/NC_CommonFunctions.cpp:1162-1170` | `if(j == niter_max_) {` / `NC_Error_Warning_0(NCout, "Warning: Maximum number of iterations is reached!");` / `}` / `break;` | 1162-1170 | **Verificado**: la salida real tiene esa línea y después `End time: …` |
| 3.1b | `NC_Error_Warning_0` imprime y no termina el programa (a diferencia de `NC_Error_Exit_0`, que hace `exit(1)`) | `src/NC_CommonFunctions.cpp:59-67`, `48-57` | `cout << errorMessage << "\n" << endl;` / `NCout << errorMessage << "\n" << endl;` (sin `exit`) / en `NC_Error_Exit_0`: `exit(1);` | 59-67 | Verificado (el proceso siguió hasta escribir resultados) |
| 3.1c | **Con FMM, la solución no convergida se usa tal cual.** Solo con BEM tradicional (`methodFMM_ == 0`) se cae a eliminación gaussiana | `src/NC_CommonFunctions.cpp:1181-1191` | `if(j >= niter_max_ && methodFMM_ == 0)` / `{` / `DirectCGS:` / `NC_Error_Warning_0(NCout, "Iteration method CGS failed, direct method is used!");` | 1181-1191 | **Verificado**: tu corrida divergida (ML-FMM) escribió `be.out/be.78` |
| 3.1d | **Código de salida 0**: `main` termina con `return(0)` sin consultar la convergencia | `src/NC_Main.cpp:270-285` | `NC_ControlProgram(NCout,iend,estimate_ram,check_normals);` … `NCout << "\nEnd time: " …` … `return(0);` | 253-268 | **Verificado**: las tres repeticiones divergidas de 24 kHz con -e 1 terminaron con `codigo_salida: 0` (`datos/experimentos/barrido_e/diagnostico/repeticion_24kHz_e1.json`) |
| 3.1e | **No existe opción para que falle en ese caso.** Opciones de línea de comandos completas: `-istart`, `-iend`, `-nitermax`, `-estimate_ram`, `-check_normals`, `-adapt_fmmlength`, `-h` | `src/NC_Main.cpp:152-190` | `printf("-istart   int : start index of iteration\n");` … `printf("-h            : this message\n");` | 144-148 (ayuda; sin `-check_normals` ni `-adapt_fmmlength`) | Verificado para lo que existe en el binario: `-nitermax` y `-estimate_ram` están en el `.exe`; `-adapt_fmmlength` y `-check_normals` **no** (solo fuente) |
| 3.1f | **El respaldo por eliminación gaussiana usa un término independiente sobrescrito.** Al salir del bucle, también al llegar al tope, el código copia la iteración de CGS sobre `zrhs`; después, si `methodFMM_ == 0`, factoriza `zcoefl` y resuelve con ese `zrhs`. Por lo que se lee, el respaldo resuelve el sistema con la iteración de CGS como término independiente, no con b. Es una lectura del código, no se ejecutó | `src/NC_CommonFunctions.cpp:1165`, `1181-1188` | `for(i=0; i<numRowsOfCoefficientMatrix_; i++) zrhs[i] = zX_j[i];` … `if(j >= niter_max_ && methodFMM_ == 0)` … `Tfactor_usy(zcoefl, numRowsOfCoefficientMatrix_);` / `Tfbelim(zcoefl, zrhs, numRowsOfCoefficientMatrix_);` | 1165, 1181-1188 | Probable (no se ha ejecutado esa ruta) |
| 3.2 | **Cambio de multinivel a un nivel, criterio 1 (por frecuencia y tamaño de malla):** con `dLamdBeL` = longitud de onda / diámetro de la malla de contorno: si > 80, BEM tradicional; si > 1,0, FMM de un nivel; si no, se estima el número de niveles y, si sale 1, también FMM de un nivel | `src/NC_Addresses.cpp:65-110` | `double dLamdBeL = waveLength_/diameterBE_,` … `thresholBEM = 80.0,` … `thresholFMM1 = 1.0;` … `if(dLamdBeL > thresholFMM1)` / `{` / `methodFMM_ = 1; // SLFMBEM is used` … `numClusterLevels_ = NC_EstimateNumLevelsMLFMM(NCout);` / `if(numClusterLevels_ == 1)` / `{` / `methodFMM_ = 1;` | 65-110 | **Verificado por comportamiento del binario** para el umbral 1,0: con `-estimate_ram`, una frecuencia por corrida, -e 0,5 cambia entre 823 y 824 Hz (c/D = 823,4) y -e 3 entre 828 y 829 Hz (c/D = 828,4), 5 Hz de separación frente a 4,98 predichos (`datos/experimentos/barrido_e/cruce_fmm/biseccion/`). El umbral 80 sigue como probable |
| 3.2b | El «diámetro» es la diagonal de la caja envolvente de los nodos de la malla de contorno (se excluyen los de la rejilla de evaluación) | `src/NC_Input.cpp:669`, `679`, `701-703` | `if(isNodeMeshOrEvalNode[i] < 0) continue;` / `crdmaxmin[j][0] -= crdmaxmin[j][1];` / `for(j=0; j<NDIM; j++) diameterBE_ += crdmaxmin[j][0]*crdmaxmin[j][0];` / `diameterBE_ = sqrt(diameterBE_);` | 667, 677, 700-701 | Probable |
| 3.2c | Número de niveles: depende del número de elementos de contorno y del área media de los elementos (o del tamaño de cluster de nivel 0 si se da en NC.inp) | `src/NC_Addresses.cpp:810-842` | `double ele_leng = sqrt(averageElementArea_), d_levs,` / `d_min = 25.0;` … `nclusroot = sqrt((double)numElementsOfBoundaryMesh_)*0.9;` … `d_levs = log10(ClusEdgL1/clu_l_min)/log10(2.0);` | 809-841 | Probable |
| 3.2d | **Criterio 2 (por clusters):** si en algún nivel la fracción de pares de clusters cancelados supera 0,75, se pasa de multinivel a un nivel (si hay menos de 50 000 incógnitas; si no, se detiene con error) | `src/NC_Addresses.cpp:66`, `72`, `269-282` | `thresholrat = 0.75,` / `Max_Dofs_FMM1 = 50000;` / `if(d_ratio[i] > thresholrat) {` / `methodFMM_ = 1;` / `numClusterLevels_ = 1;` / `if(numRowsOfCoefficientMatrix_ < Max_Dofs_FMM1) {` / `goto Labsettradibem;` / `} else {` / `NC_Error_Exit_1(NCout, "Frquency is too low, the multilevel FMBEM can not be used!",` | 66, 72, 270-277 | Verificado que el código existe: la cadena `Frquency is too low, the multilevel FMBEM can not be used!` está en el `.exe` |
| 3.3 | Cadenas exactas en NC.out (cada una en su propia línea, precedida de una línea en blanco): `CGS solver: number of iterations = <j>, relative error = <err>` y, si se llegó al máximo, `Warning: Maximum number of iterations is reached!` (antes de la anterior) | `src/NC_CommonFunctions.cpp:1167`, `1178-1179` | `NC_Error_Warning_0(NCout, "Warning: Maximum number of iterations is reached!");` / `NCout << "\nCGS solver: number of iterations = " << j << ", relative error = " << err_rel << endl;` | 1167, 1178-1179 | **Verificado**: líneas 174 y 177 de `NC78-78.out`: `Warning: Maximum number of iterations is reached!` / `CGS solver: number of iterations = 250, relative error = 999523` |
| 3.4 | **Solo en el registro de texto.** NumCalc escribe NC*.out, los resultados en `be.out/be.<n>/` (`pBoundary`, `vBoundary`, `pEvalGrid`, `vEvalGrid`) y, con `-estimate_ram`, `Memory.txt`. Ninguno de los archivos de datos lleva el estado de convergencia | `src/NC_Main.cpp:225-240`, `309`; `src/NC_PostProcessing.cpp:426-430`, `598-602` | `sprintf(filename,"NC%d-%d.out",istart_,iend);` / `NCestim.open("Memory.txt");` / `sprintf(Dfname_3d, "be.out/be.%d/pBoundary",  currentFrequency_ + 1);` / `sprintf(Dfname_3d, "be.out/be.%d/pEvalGrid",  currentFrequency_ + 1);` | 208-224, 292, 426-430, 598-602 | Verificado (son los únicos archivos que produce el binario en tus corridas) |
| 3.5 | **El FMM se puede desactivar desde NC.inp.** El octavo número de «Main Parameters I» es `methodBEM_`: 0 fuerza BEM tradicional para todas las frecuencias (las mallas de este trabajo usan 4, multinivel). El noveno, `methodSolver_`, admite 4 = eliminación gaussiana directa, sin precondicionador, solo sin FMM. El límite de 20 000 incógnitas del BEM tradicional (`Max_Dofs_TBEM`) solo se aplica cuando el programa cae solo a BEM tradicional desde un nivel, no cuando se pide con `methodBEM_ = 0` | `src/NC_Input.cpp:252-253`, `277-278`, `290`, `323`; `src/NC_Addresses.cpp:71`, `80`, `262`; `src/NC_Main.cpp:760`, `843` | `methodBEM_ = NC_String2Integer(chterms[7]);` / `methodSolver_ = NC_String2Integer(chterms[8]);` / `case 0:` `methodFMM_ = 0; // TBEM` / `if(methodSolver_ == 4) methodPreconditioner_ = 2;` / `if(methodBEM_ == 0) // for a TRBEM job` / `zcoefl = new Complex[numComponentsOfCoefficientMatrix_];` / `case 4: // direct method, usable only to the TBEM` | Input 245-246, 270-271, 283, 316; Addresses 71, 80, 260; Main 742, 825 | Probable (no se ha ejecutado con `methodBEM_ = 0`) |

**Notas**

1. Las líneas «2022» salen del fuente del commit `001351d7e1`. Donde no hay columna aparte, la línea es la misma.
2. «Verificado» en el binario se basa en cuatro tipos de evidencia: cadenas de texto en `NumCalc.exe`, la salida
   real `NC78-78.out` del 2026-09-29, los códigos de salida registrados y, como cuarto tipo, el **comportamiento
   del binario**: una constante numérica (1e-9, 250, 1,0, 80, 0,75) no deja cadena en el `.exe`, pero puede quedar
   acotada o confirmada por lo que el binario hace. Así están verificados el 250 (la divergencia se detuvo en 250),
   el 1e-9 (1.4, distribución del factor final) y el umbral 1,0 de λ/D (3.2, bisección). El 80 y el 0,75 quedan
   como «probable».
3. Algunas cadenas que el programa sí imprime (por ejemplo `Warning: Maximum number of iterations is reached!`) no
   aparecen como texto plano en el `.exe`, probablemente porque el compilador las construye por partes al pasarlas como
   `std::string`. Su ausencia en la búsqueda de cadenas no prueba que falten; esa en concreto aparece en la salida real.

## Consecuencias para el pipeline (no son afirmaciones de la tesis)

- `malla/convergencia.py` leía la tolerancia del tercer número de «Controlparameter II» (1e-6), que según 1.4b es el
  incremento de paso de frecuencias. **Corregido** (commit `9518b0c`): tolerancia 1e-9 y tope 250 como constantes,
  banderas `convergio` y `alcanzo_tope` independientes, detección de ILU fallido y de respaldo directo. La auditoría
  de todos los NC*.out del disco no cambió ninguna clasificación.
- El documento de metodología decía «el resolvedor itera hasta que el error baja de 1e-6». **Corregido** a 1e-9,
  con la aclaración de qué mide el factor (1.5).
- El «999 523» de la divergencia es, por 1.5, el residuo de la iteración 250 dividido por el de la primera
  iteración: el residuo creció unas 10⁶ veces respecto a la primera iteración. No es un residuo relativo a ‖b‖.

## Experimento opcional: la causa de la divergencia

No está en el camino crítico. La divergencia de 24 kHz con -e 1 se explica hoy como un mecanismo compatible
(convergencia irregular de CGS), no como causa demostrada. Por 3.5, el FMM se puede desactivar desde NC.inp, así que
hay un experimento que la demostraría: resolver 24 kHz con la malla de -e 1 (21 360 incógnitas) sin FMM.

- **Memoria:** la matriz densa ocupa 21 360² × 16 bytes = 7,3 GB (6,8 GiB), más el ILU. Entra en esta máquina.
- **Diseño, dos corridas en vez de una.** Por 3.1f, si CGS falla sin FMM, el respaldo gaussiano resolvería con el
  término independiente sobrescrito: su resultado no sirve para decidir nada. Por eso:
  1. `methodBEM_ = 0`, `methodSolver_ = 0` (CGS sin FMM). Si converge, el culpable es la aproximación FMM del
     operador. Si no converge, el problema está en el sistema o en CGS.
  2. `methodBEM_ = 0`, `methodSolver_ = 4` (eliminación gaussiana directa, con b intacto). Da la solución de
     referencia. Si la de la corrida 1 coincide con ella, CGS sin FMM es fiable; si Gauss también da algo anómalo,
     el sistema está mal condicionado a esa frecuencia.
- **Costo:** una factorización densa de ese tamaño en un solo hilo tarda horas; no se ha medido.

## Lo que no se pudo verificar

1. **El commit exacto del binario.** Solo se sabe que se compiló el 2022-08-26 desde la rama `develop`, según su
   readme. El commit `001351d7e1` es el más probable, pero es un supuesto.
2. **Que el residuo de la recurrencia de CGS coincida con el residuo verdadero** `D·(b − A·x)`. Matemáticamente
   coinciden; numéricamente pueden separarse, y el código no recalcula el residuo verdadero.
3. **La norma de b o del residuo inicial.** El código no la calcula ni la imprime, así que no se puede reconstruir
   ‖b − A·x‖/‖b‖ desde NC.out.
4. **«Galerkin».** No se encontró. La clasificación como colocación (2.4) es una lectura de la estructura del
   código, que no usa ese nombre salvo en un comentario de posprocesado.
5. **El tratamiento de la singularidad** al integrar sobre el propio elemento: se vio la subdivisión en
   subelementos (`NC_GenerateSubelements`), pero no se verificó su método.
6. **Los valores numéricos en el binario** β = i/k y los umbrales 80 y 0,75: coinciden en los dos fuentes, pero
   no pueden leerse en el `.exe` sin desensamblarlo. El 1e-9 (1.4) y el umbral 1,0 (3.2) salieron de esta lista:
   están verificados por comportamiento del binario.
7. **El respaldo por eliminación gaussiana (3.1f).** Que resuelva con el término independiente sobrescrito es una
   lectura del código; esa ruta no se ha ejecutado.
