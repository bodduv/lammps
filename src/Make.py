#!/usr/bin/env python2

# Make.py tool for managing packages and their auxiliary libs,
#   auto-editing machine Makefiles, and building LAMMPS
# Syntax: Make.py -h (for help)
# Notes: should be compatible with python 2.7 and 3.x thanks to 'futurize'

from __future__ import print_function
import sys,os,re,copy,subprocess,platform

# switch abbrevs
# switch classes = created class for each switch
# lib classes = auxiliary package libs
# build classes = build options with defaults
# make classes = makefile options with no defaults
# setargs = makefile settings
# actionargs = allowed actions (also lib-dir and machine)
# lib build flags are set if lib is built, for use with zoutput

abbrevs = "adhjmoprsvz"

switchclasses = ("actions","dir","help","jmake","makefile",
                 "output","packages","redo","settings","verbose","zoutput")
libclasses = ("atc","awpmd","colvars","cuda","gpu","h5md",
              "meam","poems","python","qmmm","voronoi")
buildclasses = ("intel","kokkos")
makeclasses = ("cc","flags","mpi","fft","jpg","png")

setargs = ("gzip","#gzip","ffmpeg","#ffmpeg","smallbig","bigbig","smallsmall","exceptions","#exceptions")
actionargs = ("lib-all","file","clean","exe")

gpubuildflag = 0

# ----------------------------------------------------------------
# functions
# ----------------------------------------------------------------

# if flag = 1, print txt and exit
# if flag = 0, print txt as warning and do not exit

def error(txt,flag=1):
  if flag:
    print("ERROR:",txt)
    sys.exit()
  else:
    print("WARNING:",txt)

# store command-line args as sw = dict of key/value
# key = switch word, value = list of following args
# order = list of switches in order specified
# enforce no switch more than once
  
def parse_args(args):
  narg = len(args)
  sw = {}
  order = []
  iarg = 0
  while iarg < narg:
    if args[iarg][0] != '-': error("Arg %s is not a switch" % args[iarg])
    switch = args[iarg][1:]
    if switch in sw: error("Duplicate switch %s" % args[iarg])
    order.append(switch)
    first = iarg+1
    last = first
    while last < narg and args[last][0] != '-': last += 1
    sw[switch] = args[first:last]
    iarg = last
  return sw,order

# convert info in switches dict back to a string, in switch_order

def switch2str(switches,switch_order):
  txt = ""
  for switch in switch_order:
    if txt: txt += ' '
    txt += "-%s" % switch
    txt += ' ' + ' '.join(switches[switch])
  return txt

# check if compiler works with ccflags on dummy one-line tmpauto.cpp file
# return 1 if successful, else 0
# warn = 1 = print warning if not successful, warn = 0 = no warning
# NOTE: unrecognized -override-limits can leave verride-limits file

def compile_check(compiler,ccflags,warn):
  open("tmpauto.cpp",'w').write("int main(int, char **) {}\n")
  tmp = "%s %s -c tmpauto.cpp" % (compiler,ccflags)
  txt = subprocess.check_output(tmp,stderr=subprocess.STDOUT,shell=True).decode()
  flag = 1
  if txt or not os.path.isfile("tmpauto.o"):
    flag = 0
    if warn:
      print(tmp)
      if txt: print(txt)
      else: print("compile produced no output")
  os.remove("tmpauto.cpp")
  if os.path.isfile("tmpauto.o"): os.remove("tmpauto.o")
  return flag

# check if linker works with linkflags and libs on tmpauto.o file
# return 1 if successful, else 0
# warn = 1 = print warning if not successful, warn = 0 = no warning

def link_check(linker,linkflags,libs,warn):
  open("tmpauto.cpp",'w').write("int main(int, char **) {}\n")
  tmp = "%s %s -o tmpauto tmpauto.cpp %s" % (linker,linkflags,libs)
  txt = subprocess.check_output(tmp,stderr=subprocess.STDOUT,shell=True).decode()
  flag = 1
  if txt or not os.path.isfile("tmpauto"):
    flag = 0
    if warn:
      print(tmp)
      if txt: print(txt)
      else: print("link produced no output")
  os.remove("tmpauto.cpp")
  if os.path.isfile("tmpauto"): os.remove("tmpauto")
  return flag

# ----------------------------------------------------------------
# switch classes, one per single-letter switch
# ----------------------------------------------------------------

# actions

class Actions(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    
  def help(self):
    return """
-a action1 action2 ...
  possible actions = lib-all, lib-dir, file, clean, exe or machine
    machine is a Makefile.machine suffix
  actions can be specified in any order
  each action can appear only once
    lib-dir can appear multiple times for different dirs
  some actions depend on installed packages
    installed packages = currently installed + result of -p switch
  actions are invoked in this order, independent of specified order
  (1) lib-all or lib-dir = build auxiliary libraries
    lib-all builds all auxiliary libs needed by installed packages
    lib-dir builds a specific lib whether package installed or not
      dir is any dir in lib directory (atc, cuda, meam, etc) except linalg
  (2) file = create a new src/MAKE/MINE/Makefile.auto
    if file not specified, existing Makefile.auto is NOT changed
      except by -m switch, which will copy Makefile.machine to Makefile.auto
      note that exe action can add an -m switch, as described below
    if file is specified, new Makefile.auto is created
      if "-m machine" specified (or added by exe),
        start with existing Makefile.machine, else existing Makefile.auto
      if "-m none" specified, start Makefile.auto from scratch
        must use -cc and -mpi switches to specify compiler and MPI
      settings for these switches will alter Makefile.auto
        -s, -intel, -kokkos, -cc, -mpi, -fft, -jpg, -png
      if these accelerator packages are installed, they induce settings
        that will alter Makefile.auto: opt, user-omp, user-intel, kokkos
     use -z switch to copy final Makefile.auto to new filename
  (3) clean = invoke "make clean-auto" to insure clean build on current files
    useful if compiler flags have changed
  (4) exe or machine = build LAMMPS
    machine can be any existing Makefile.machine suffix
      machine is converted to "exe" action, and additionally:
        "-m machine" is added if -m switch is not specified
        "-o machine" is added if -o switch is not specified
        if either "-m"  or "-o" are specified, they are not overridden
    does not invoke any lib builds, since libs could be previously built
    exe ALWAYS builds using src/MAKE/MINE/Makefile.auto
      if file action also specified, it creates a new Makefile.auto
      else if -m switch specified,
        existing Makefile.machine is copied to create Makefile.auto
      else Makefile.auto must already exist and is not changed
    build produces src/lmp_auto, or error message if unsuccessful
      use -o switch to copy src/lmp_auto to new filename
      use -z switch to copy src/MAKE/MINE/Makefile.auto to new filename
"""
  
  def check(self):
    if not self.inlist: error("-a args are invalid")
    libs = []
    cleans = []
    files = []
    exes = []
    for one in self.inlist:
      if one.startswith("lib-"):
        lib = one[4:]
        if lib != "all" and lib not in libclasses: error("Actions are invalid")
        libs.append(one)
      elif one == "file":
        files.append(one)
      elif one == "clean":
        cleans.append(one)
      elif one == "exe":
        exes.append(one)
      # one action can be unknown, must be a machine (checked in setup)
      else:
        exes.append(one)
    if len(set(libs)) != len(libs) or \
       len(cleans) > 1 or len(files) > 1 or len(exes) > 1:
      error("Actions are invalid")
    self.alist = [action for actions in [libs,cleans,files,exes] \
                           for action in actions]

  # dedup list of actions concatenated from two lists
  # current self.inlist = specified -a switch + redo command -a switch
  # specified exe/machine action replaces redo exe/machine action
  # operates on and replaces self.inlist
    
  def dedup(self):
    alist = []
    exemachine = 0
    for one in self.inlist:
      if one == "exe" or (one not in actionargs and not one.startswith("lib-")):
        if exemachine: continue
        exemachine = 1
      if one not in alist: alist.append(one)
    self.inlist = alist
  
  # if last action is unknown, assume machine and convert to exe
  # only done if action is a suffix for an existing Makefile.machine
  # return machine if conversion done, else None
    
  def setup(self):
    machine = self.alist[-1]
    if machine in actionargs or machine.startswith("lib-"): return None
    make = MakeReader(machine,2)
    self.alist[-1] = "exe"
    return machine

  # build one or more auxiliary package libraries
  
  def lib(self,suffix):
    if suffix != "all":
      print("building",suffix,"library ...")
      txt = "%s.build()" % suffix
      exec(txt)
    else:
      final = packages.final
      for one in packages.lib:
        if final[one]:
          if "user" in one: pkg = one[5:]
          else: pkg = one
          print("building",pkg,"library ...")
          txt = "%s.build()" % pkg
          exec(txt)

  # read Makefile.machine
  # if caller = "file", edit via switches
  # if caller = "exe", just read
  # write out new Makefile.auto
  
  def file(self,caller):

    # if caller="file", create from mpi or read from Makefile.machine or auto
    # if caller="exe" and "file" action already invoked, read from auto
    # if caller="exe" and no "file" action, read from Makefile.machine or auto
    
    if caller == "file":
      if makefile and makefile.machine == "none":
        if cc and mpi: machine = "mpi"
        else: error("Cannot create makefile unless -cc and -mpi are used")
      elif makefile: machine = makefile.machine
      else: machine = "auto"
    elif caller == "exe" and "file" in self.alist:
      machine = "auto"
    elif caller == "exe" and "file" not in self.alist:
      if makefile and makefile.machine == "none":
        error("Cannot build with makefile = none")
      elif makefile: machine = makefile.machine
      else: machine = "auto"

    make = MakeReader(machine,1)

    # change makefile settings to user specifications
        
    precompiler = ""
    if caller == "file":
            
      # add compiler/linker and default CCFLAGS,LINKFLAGS
      # if cc.wrap, add wrapper setting for mpi = ompi/mpich
      # precompiler = env variable setting for OpenMPI wrapper compiler
      
      if cc:
        make.setvar("CC",cc.compiler)
        make.setvar("LINK",cc.compiler)
        if cc.wrap:
          if cc.wrap == "nvcc":
            wrapper = os.path.abspath("../lib/kokkos/config/nvcc_wrapper")
          else: wrapper = cc.wrap
          abbrev = cc.abbrev
          if abbrev == "mpi":
            if cc.parent == "mpich":
              make.addvar("CC","-cxx=%s" % wrapper)
              make.addvar("LINK","-cxx=%s" % wrapper)
            elif cc.parent == "openmpi":
              make.addvar("export OMPI_CXX",wrapper,"cc")
              precompiler = "env OMPI_CXX=%s " % wrapper
            else: error("Could not add MPI wrapper compiler, " +
                        "did not recognize OpenMPI or MPICH")
        make.setvar("CCFLAGS","-g")
        make.addvar("CCFLAGS","-O3")
        make.setvar("LINKFLAGS","-g")
        make.addvar("LINKFLAGS","-O")
        
      # add MPI settings

      if mpi:
        make.delvar("MPI_INC","*")
        make.delvar("MPI_PATH","*")
        make.delvar("MPI_LIB","*")
        if mpi.style == "mpi":
          make.addvar("MPI_INC","-DMPICH_SKIP_MPICXX")
          make.addvar("MPI_INC","-DOMPI_SKIP_MPICXX=1")
        elif mpi.style == "mpich":
          make.addvar("MPI_INC","-DMPICH_SKIP_MPICXX")
          make.addvar("MPI_INC","-DOMPI_SKIP_MPICXX=1")
          if mpi.dir: make.addvar("MPI_INC","-I%s/include" % mpi.dir)
          if mpi.dir: make.addvar("MPI_PATH","-L%s/lib" % mpi.dir)
          make.addvar("MPI_LIB","-lmpich")
          make.addvar("MPI_LIB","-lmpl")
          make.addvar("MPI_LIB","-lpthread")
        elif mpi.style == "ompi":
          make.addvar("MPI_INC","-DMPICH_SKIP_MPICXX")
          make.addvar("MPI_INC","-DOMPI_SKIP_MPICXX=1")
          if mpi.dir: make.addvar("MPI_INC","-I%s/include" % mpi.dir)
          if mpi.dir: make.addvar("MPI_PATH","-L%s/lib" % mpi.dir)
          make.addvar("MPI_LIB","-lmpi")
          make.addvar("MPI_LIB","-lmpi_cxx")
        elif mpi.style == "serial":
          make.addvar("MPI_INC","-I../STUBS")
          make.addvar("MPI_PATH","-L../STUBS")
          make.addvar("MPI_LIB","-lmpi_stubs")

      # add accelerator package CCFLAGS and LINKFLAGS and variables
          
      compiler = precompiler + ' '.join(make.getvar("CC"))
      linker = precompiler + ' '.join(make.getvar("LINK"))
            
      final = packages.final
      if final["opt"]:
        if compile_check(compiler,"-restrict",0):
          make.addvar("CCFLAGS","-restrict")
          
      if final["user-omp"]:
        if compile_check(compiler,"-fopenmp",1):
          make.addvar("CCFLAGS","-fopenmp")
          make.addvar("LINKFLAGS","-fopenmp")
        if compile_check(compiler,"-restrict",0):
          make.addvar("CCFLAGS","-restrict")

      if final["user-intel"]:
        if intel.mode == "cpu":
          make.delvar("CCFLAGS","-O*")
          make.addvar("CCFLAGS","-O2")
          if compile_check(compiler,"-openmp",1):
            make.addvar("CCFLAGS","-openmp")
          if compile_check(compiler,"-restrict",1):
            make.addvar("CCFLAGS","-restrict")
          if compile_check(compiler,"-no-offload",1):
            make.addvar("CCFLAGS","-no-offload")
          if compile_check(compiler,"-fno-alias",1):
            make.addvar("CCFLAGS","-fno-alias")
          if compile_check(compiler,"-ansi-alias",1):
            make.addvar("CCFLAGS","-ansi-alias")
          if compile_check(compiler,"-xAVX",1):
            make.addvar("CCFLAGS","-xAVX")
          if compile_check(compiler,"-fp-model fast=2",1):
            make.addvar("CCFLAGS","-fp-model fast=2")
          if compile_check(compiler,"-no-prec-div",1):
            make.addvar("CCFLAGS","-no-prec-div")
          if compile_check(compiler,"-override-limits",1):
            make.addvar("CCFLAGS","-override-limits")
          make.addvar("CCFLAGS","-DLAMMPS_MEMALIGN=64")
          make.delvar("CCFLAGS","-DLMP_INTEL_OFFLOAD")

          make.delvar("LINKFLAGS","-O*")
          make.addvar("LINKFLAGS","-O2")
          if link_check(linker,"-openmp","",1):
            make.addvar("LINKFLAGS","-openmp")
          if link_check(linker,"-xAVX","",1):
            make.addvar("LINKFLAGS","-xAVX")
          if link_check(linker,"-fpmodel fast=2","",1):
            make.addvar("LINKFLAGS","-fpmodel fast=2")
          if link_check(linker,"-no-prec-div","",1):
            make.addvar("LINKFLAGS","-no-prec-div")
          if link_check(linker,"-override-limits","",1):
            make.addvar("LINKFLAGS","-override-limits")
          make.delvar("LINKFLAGS","-offload")

          if link_check(linker,"","-ltbbmalloc",1):
            make.addvar("LIB","-ltbbmalloc")
          if link_check(linker,"","-ltbbmalloc_proxy",1):
            make.addvar("LIB","-ltbbmalloc_proxy")
            
        elif intel.mode == "phi":
          if compile_check(compiler,"-fopenmp",1):
            make.addvar("CCFLAGS","-fopenmp")
            make.addvar("LINKFLAGS","-fopenmp")
          make.addvar("CCFLAGS","-DLAMMPS_MEMALIGN=64")
          if compile_check(compiler,"-restrict",1):
            make.addvar("CCFLAGS","-restrict")
          if compile_check(compiler,"-xHost",1):
            make.addvar("CCFLAGS","-xHost")
          make.addvar("CCFLAGS","-DLMP_INTEL_OFFLOAD")
          if compile_check(compiler,"-fno-alias",1):
            make.addvar("CCFLAGS","-fno-alias")
          if compile_check(compiler,"-ansi-alias",1):
            make.addvar("CCFLAGS","-ansi-alias")
          if compile_check(compiler,"-override-limits",1):
            make.addvar("CCFLAGS","-override-limits")
          if compile_check(compiler,'-offload-option,mic,compiler,' +
                          '"-fp-model fast=2 -mGLOB_default_function_attrs=' +
                          '\\"gather_scatter_loop_unroll=4\\""',1):
            make.addvar("CCFLAGS",'-offload-option,mic,compiler,' +
                        '"-fp-model fast=2 -mGLOB_default_function_attrs=' +
                        '\\"gather_scatter_loop_unroll=4\\""')
          if link_check(linker,"-offload","",1):
            make.addvar("LINKFLAGS","-offload")

      if final["kokkos"]:
        if kokkos.mode == "omp":
          make.delvar("KOKKOS_DEVICES","*")
          make.delvar("KOKKOS_ARCH","*")
          make.addvar("KOKKOS_DEVICES","OpenMP","lmp")
          if kokkos.archcpu:
            make.addvar("KOKKOS_ARCH",kokkos.archcpu,"lmp")
        elif kokkos.mode == "cuda":
          make.delvar("KOKKOS_DEVICES","*")
          make.delvar("KOKKOS_ARCH","*")
          make.addvar("KOKKOS_DEVICES","Cuda, OpenMP","lmp")
          if kokkos.archgpu:
            if kokkos.archgpu[0] == "3": value = "Kepler" + kokkos.archgpu
            elif kokkos.archgpu[0] == "2": value = "Fermi" + kokkos.archgpu
            else: error("Unrecognized Kokkos archgpu setting")
          if kokkos.archcpu: value += ", %s" % kokkos.archcpu
          make.addvar("KOKKOS_ARCH",value,"lmp")
        elif kokkos.mode == "phi":
          make.delvar("KOKKOS_DEVICES","*")
          make.delvar("KOKKOS_ARCH","*")
          make.addvar("KOKKOS_DEVICES","OpenMP","lmp")
          make.addvar("KOKKOS_ARCH","KNC","lmp")

      # add LMP_INC ifdef settings
      
      if settings:
        list = settings.inlist
        for one in list:
          if one == "gzip": make.addvar("LMP_INC","-DLAMMPS_GZIP")
          elif one == "#gzip": make.delvar("LMP_INC","-DLAMMPS_GZIP")
          elif one == "ffmpeg": make.addvar("LMP_INC","-DLAMMPS_FFMPEG")
          elif one == "#ffmpeg": make.delvar("LMP_INC","-DLAMMPS_FFMPEG")
          elif one == "smallbig":
            make.delvar("LMP_INC","-DLAMMPS_BIGBIG")
            make.delvar("LMP_INC","-DLAMMPS_SMALLSMALL")
          elif one == "bigbig":
            make.delvar("LMP_INC","-DLAMMPS_SMALLBIG")
            make.delvar("LMP_INC","-DLAMMPS_SMALLSMALL")
            make.addvar("LMP_INC","-DLAMMPS_BIGBIG")
          elif one == "smallsmall":
            make.delvar("LMP_INC","-DLAMMPS_SMALLBIG")
            make.delvar("LMP_INC","-DLAMMPS_BIGBIG")
            make.addvar("LMP_INC","-DLAMMPS_SMALLSMALL")
          elif one == "exceptions": make.addvar("LMP_INC","-DLAMMPS_EXCEPTIONS")
          elif one == "#exception": make.delvar("LMP_INC","-DLAMMPS_EXCEPTIONS")
          
      # add FFT, JPG, PNG settings

      if fft:
        make.delvar("FFT_INC","*")
        make.delvar("FFT_PATH","*")
        make.delvar("FFT_LIB","*")
        if fft.mode == "none": make.addvar("FFT_INC","-DFFT_NONE")
        else:
          make.addvar("FFT_INC","-DFFT_%s" % fft.mode.upper())
          make.addvar("FFT_LIB",fft.lib)
          if fft.dir:
            make.addvar("FFT_INC","-I%s/include" % fft.dir)
            make.addvar("FFT_PATH","-L%s/lib" % fft.dir)
          else:
            if fft.incdir: make.addvar("FFT_INC","-I%s" % fft.incdir)
            if fft.libdir: make.addvar("FFT_PATH","-L%s" % fft.libdir)

      if jpg:
        if jpg.on == 0:
          make.delvar("LMP_INC","-DLAMMPS_JPEG")
          make.delvar("JPG_LIB","-ljpeg")
        else:
          make.addvar("LMP_INC","-DLAMMPS_JPEG")
          make.addvar("JPG_LIB","-ljpeg")
          if jpg.dir:
            make.addvar("JPG_INC","-I%s/include" % jpg.dir)
            make.addvar("JPG_PATH","-L%s/lib" % jpg.dir)
          else:
            if jpg.incdir: make.addvar("JPG_INC","-I%s" % jpg.incdir)
            if jpg.libdir: make.addvar("JPG_PATH","-L%s" % jpg.libdir)

      if png:
        if png.on == 0:
          make.delvar("LMP_INC","-DLAMMPS_PNG")
          make.delvar("JPG_LIB","-lpng")
        else:
          make.addvar("LMP_INC","-DLAMMPS_PNG")
          make.addvar("JPG_LIB","-lpng")
          if png.dir:
            make.addvar("JPG_INC","-I%s/include" % png.dir)
            make.addvar("JPG_PATH","-L%s/lib" % png.dir)
          else:
            if png.incdir: make.addvar("JPG_INC","-I%s" % png.incdir)
            if png.libdir: make.addvar("JPG_PATH","-L%s" % png.libdir)

      # finally after all other settings, add explicit flags

      if flags:
        for var,action,flist in flags.flags:
          values = make.getvar(var)
          if values == None:
            error("Flags for a non-existent Makefile.auto variable")
          for flag in flist:
            flag = "-" + flag
            if action == "add": make.addvar(var,flag)
            elif action == "del": make.delvar(var,flag)

    # set self.stubs if Makefile.auto uses STUBS lib in MPI settings

    if make.getvar("MPI_LIB") and "-lmpi_stubs" in make.getvar("MPI_LIB"):
      self.stubs = 1
    else: self.stubs = 0
    
    # write out Makefile.auto
    # unless caller = "exe" and "file" action already invoked
    
    if caller == "file" or "file" not in self.alist:
      # make certain that 'MAKE/MINE' folder exists.
      subprocess.check_output("mkdir -p %s/MAKE/MINE" % dir.src,stderr=subprocess.STDOUT,shell=True)
      make.write("%s/MAKE/MINE/Makefile.auto" % dir.src,1)
      print("Created src/MAKE/MINE/Makefile.auto")
      
    # test full compile and link
    # unless caller = "file" and "exe" action will be invoked later

    if caller == "file" and "exe" in self.alist: return
    compiler = precompiler + ' '.join(make.getvar("CC"))
    ccflags = ' '.join(make.getvar("CCFLAGS"))
    linker = precompiler + ' '.join(make.getvar("LINK"))
    linkflags = ' '.join(make.getvar("LINKFLAGS"))
    libs = ' '.join(make.getvar("LIB"))
    if not compile_check(compiler,ccflags,1):
      error("Test of compilation failed")
    if not link_check(linker,linkflags,libs,1): error("Test of link failed")

  # invoke "make clean-auto" to force clean before build
    
  def clean(self):
    txt = "cd %s; make clean-auto" % dir.src
    subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
    print("Performed make clean-auto")

  # build LAMMPS using Makefile.auto and -j setting
  # invoke self.file() first, to test makefile compile/link
  # delete existing lmp_auto, so can detect if build fails
  # build STUBS lib (if unbuilt) if Makefile.auto MPI settings need it
    
  def exe(self):
    self.file("exe")
    subprocess.check_output("cd %s; rm -f lmp_auto" % dir.src,stderr=subprocess.STDOUT,shell=True)
    if self.stubs and not os.path.isfile("%s/STUBS/libmpi_stubs.a" % dir.src):
      print("building serial STUBS library ...")
      tmp = "cd %s/STUBS; make clean; make" % dir.src
      txt = subprocess.check_output(tmp,stderr=subprocess.STDOUT,shell=True).decode()
      if not os.path.isfile("%s/STUBS/libmpi_stubs.a" % dir.src):
        print(txt)
        error('Unsuccessful "make stubs"')
      print("Created src/STUBS/libmpi_stubs.a")

    # special hack for shannon GPU cluster
    # must use "srun make" if on it and building w/ GPU package, else just make
    # this is b/c Cuda libs are not all available on host

    make = "make"
    if "shannon" == platform.node() and packages.final["gpu"]:
      make = "srun make"
      
    if jmake: tmp = "cd %s; %s -j %d auto" % (dir.src,make,jmake.n)
    else: tmp = "cd %s; %s auto" % (dir.src,make)
    
    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(tmp,shell=True)
    else:
      print(tmp)
      try: subprocess.check_output(tmp,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/lmp_auto" % dir.src):
      error('Unsuccessful "make auto"')
    elif not output: print("Created src/lmp_auto")
    
# dir switch

class Dir(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
      
  def help(self):
    return """
-d dir
  dir = LAMMPS home dir
  if -d not specified, working dir must be lammps/src
"""

  def check(self):
    if self.inlist != None and len(self.inlist) != 1:
      error("-d args are invalid")
      
  # if inlist = None, check that cwd = lammps/src
  # store cwd and lammps dir
  # derive src,make,lib dirs from lammps dir
  # check that they all exist
  
  def setup(self):
    self.cwd = os.getcwd()
    if self.inlist == None: self.lammps = ".."
    else: self.lammps = self.inlist[0]
    self.lammps = os.path.realpath(self.lammps)
    self.src = self.lammps + "/src"
    self.make = self.lammps + "/src/MAKE"
    self.lib = self.lammps + "/lib"
    if not os.path.isdir(self.lammps): error("LAMMPS home dir is invalid")
    if not os.path.isdir(self.src): error("LAMMPS src dir is invalid")
    if not os.path.isdir(self.lib): error("LAMMPS lib dir is invalid")

# help switch

class Help(object):
  def __init__(self,list): pass

  def help(self):
    return """
Syntax: Make.py switch args ...
  switches can be listed in any order
  help switch:
    -h prints help and syntax for all other specified switches
  switch for actions:
    -a lib-all, lib-dir, clean, file, exe or machine
    list one or more actions, in any order
    machine is a Makefile.machine suffix
  one-letter switches:
    -d (dir), -j (jmake), -m (makefile), -o (output), -p (packages),
    -r (redo), -s (settings), -v (verbose), -z (makefile output)
  switches for libs:
    -atc, -awpmd, -colvars, -cuda, -gpu, -h5md,
    -meam, -poems, -python, -qmmm, -voronoi
  switches for build and makefile options:
    -intel, -kokkos, -cc, -flags, -mpi, -fft, -jpg, -png
"""

# jmake switch
  
class Jmake(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
  
  def help(self):
    return """
-j N
  use N procs for performing parallel make commands
  used when building a lib or LAMMPS itself
  if -j not specified, serial make commands run on single core
"""

  def check(self):
    if len(self.inlist) != 1: error("-j args are invalid")
    if not self.inlist[0].isdigit(): error("-j args are invalid")
    n = int(self.inlist[0])
    if n <= 0: error("-j args are invalid")
    self.n = n
        
# makefile switch

class Makefile(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
  
  def help(self):
    return """
-m machine
  use Makefile.machine under src/MAKE as starting point to create Makefile.auto
  if machine = "none", file action will create Makefile.auto from scratch
    must use -cc and -mpi switches to specify compiler and MPI
  if -m not specified, file/exe actions alter existing Makefile.auto
"""
  
  def check(self):
    if len(self.inlist) != 1: error("-m args are invalid")
    self.machine = self.inlist[0]
    
# output switch

class Output(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)

  def help(self):
    return """
-o machine
  copy final src/lmp_auto to lmp_machine in working dir
  if -o not specified, exe action only produces src/lmp_auto
"""

  def check(self):
    if len(self.inlist) != 1: error("-o args are invalid")
    self.machine = self.inlist[0]

# packages switch
  
class Packages(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)

  def help(self):
    return """
-p = package1 package2 ...
  list of packages to install or uninstall in order specified
  operates on set of packages currently installed
  valid package names:
    any LAMMPS standard or user package (type "make package" to see list)
    prefix by yes/no to install/uninstall (see abbrevs)
      yes-molecule, yes-user-atc, no-molecule, no-user-atc
  can use LAMMPS categories (type "make package" to see list)
    all = all standard and user packages (also none = no-all)
    std (or standard) = all standard packages
    user = all user packages
    lib = all standard and user packages with auxiliary libs
  can abbreviate package names and yes/no
    omp = user-omp = yes-user-omp
    ^omp = ^user-omp = no-user-omp
    user = yes-user, ^user = no-user
    all = yes-all, ^all = none = no-all
  when action performed, list is processed in order,
    as if typed "make yes/no" for each
  if "orig" or "original" is last package in list,
    set of installed packages will be restored to original (current) list
    after "build" action is performed
  if -p not specified, currently installed packages are not changed
"""

  def check(self):
    if self.inlist != None and not self.inlist: error("-p args are invalid")

  def setup(self):
      
    # extract package lists from src/Makefile
    # remove names from lib that there are not Make.py lib-classes for
    # most don't actually have libs, so nothing to control from Make.py
    
    make = MakeReader("%s/Makefile" % dir.src)
    std = make.getvar("PACKAGE")
    user = make.getvar("PACKUSER")
    lib = make.getvar("PACKLIB")
    lib.remove("kim")
    lib.remove("kokkos")
    lib.remove("user-molfile")
    lib.remove("python")
    lib.remove("user-quip")
    all = std + user
    
    # plist = command line args expanded to yes-package or no-package
        
    plist = []
    if self.inlist:
      for one in self.inlist:
        if one in std:
          plist.append("yes-%s" % one)
        elif one in user:
          plist.append("yes-%s" % one)
        elif "user-"+one in user:
          plist.append("yes-user-%s" % one)
        elif one == "std" or one == "standard" or one == "user" or \
              one == "lib" or one == "all": plist.append("yes-%s" % one)
        elif one.startswith("yes-"):
          if one[4:] in std: plist.append("yes-%s" % one[4:])
          elif one[4:] in user: plist.append("yes-%s" % one[4:])
          elif "user-"+one[4:] in user: plist.append("yes-user-%s" % one[4:])
          elif one == "yes-std" or one == "yes-standard" or \
                one == "yes-user" or one == "yes-lib" or one == "yes-all":
            plist.append("yes-%s" % one[4:])
          else: error("Invalid package name %s" % one)
        elif one.startswith("no-"):
          if one[3:] in std: plist.append("no-%s" % one[3:])
          elif one[3:] in user: plist.append("no-%s" % one[3:])
          elif "user-"+one[3:] in user: plist.append("no-user-%s" % one[3:])
          elif one == "no-std" or one == "no-standard" or one == "no-user" or \
              one == "no-lib" or one == "no-all":
            plist.append("no-%s" % one[3:])
          else: error("Invalid package name %s" % one)
        elif one.startswith('^'):
          if one[1:] in std: plist.append("no-%s" % one[1:])
          elif one[1:] in user: plist.append("no-%s" % one[1:])
          elif "user-"+one[1:] in user: plist.append("no-user-%s" % one[1:])
          elif one == "^std" or one == "^standard" or one == "^user" or \
              one == "^lib" or one == "^all": plist.append("no-%s" % one[1:])
          else: error("Invalid package name %s" % one)
        elif one == "none": plist.append("no-all")
        elif one == "orig": plist.append(one)
        else: error("Invalid package name %s" % one)
      if "orig" in plist and plist.index("orig") != len(plist)-1:
        error('-p orig arg must be last')
      if plist.count("orig") > 1: error('-p orig arg must be last')

    # original = dict of all packages
    # key = package name, value = 1 if currently installed, else 0

    original = {}
    tmp = "cd %s; make ps" % dir.src
    output = subprocess.check_output(tmp,stderr=subprocess.STDOUT,shell=True).decode().split('\n')
    pattern = "Installed\s+(\w+): package (\S+)"
    for line in output:
      m = re.search(pattern,line)
      if not m: continue
      pkg = m.group(2).lower()
      if pkg not in all: error('Package list does not match "make ps" results')
      if m.group(1) == "NO": original[pkg] = 0      
      elif m.group(1) == "YES": original[pkg] = 1

    # final = dict of all packages after plist applied to original
    # key = package name, value = 1 if installed, else 0
        
    final = copy.deepcopy(original)
    for i,one in enumerate(plist):
      if "yes" in one:
        pkg = one[4:]
        yes = 1
      else:
        pkg = one[3:]
        yes = 0
      if pkg in all:
        final[pkg] = yes
      elif pkg == "std" or pkg == "standard":
        for pkg in std: final[pkg] = yes
      elif pkg == "user":
        for pkg in user: final[pkg] = yes
      elif pkg == "lib":
        for pkg in lib: final[pkg] = yes
      elif pkg == "all":
        for pkg in all: final[pkg] = yes

    self.std = std
    self.user = user
    self.lib = lib
    self.all = all
    self.plist = plist
    self.original = original
    self.final = final
    
  # install packages in plist
    
  def install(self):
    if self.plist: print("Installing packages ...")
    for one in self.plist:
      if one == "orig": continue
      subprocess.check_output("cd %s; make %s" % (dir.src,one),stderr=subprocess.STDOUT,shell=True)
    if self.plist and verbose:
      txt = subprocess.check_output("cd %s; make ps" % dir.src,stderr=subprocess.STDOUT,shell=True).decode()
      print("Package status after installation:")
      print(txt)
      
  # restore packages to original list if requested
  # order of re-install should not matter matter b/c of Depend.sh
  
  def uninstall(self):
    if not self.plist or self.plist[-1] != "orig": return
    print("Restoring packages to original state ...")
    subprocess.check_output("cd %s; make no-all" % dir.src,stderr=subprocess.STDOUT,shell=True)
    for one in self.all:
      if self.original[one]:
        subprocess.check_output("cd %s; make yes-%s" % (dir.src,one),stderr=subprocess.STDOUT,shell=True)
    if verbose:
      txt = subprocess.check_output("cd %s; make ps" % dir.src,stderr=subprocess.STDOUT,shell=True).decode()
      print("Restored package status:")
      print(txt)
      
# redo switch
    
class Redo(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
  
  def help(self):
    return """
-r file label1 label2 ...
  all args are optional
  invoke Make.py commands from a file
    other specified switches are merged with file commands (see below)
  redo file format:
    blank lines and lines starting with "#" are skipped
    other lines are treated as commands
    each command is a list of Make.py args, as if typed at command-line
    commands can have leading label, followed by ":"
    commands cannot contain a "-r" switch
  if no args, execute previous command, which is stored in src/Make.py.last
  if one arg, execute all commands from specified file
    unlabeled or labeled commands are all executed
  if multiple args, execute only matching labeled commands from file
  if other switches are specified,
    if file command does not have the switch, it is added
    if file command has the switch, the specified switch replaces it
    except if -a (action) switch is both specified and in the file command,
      two sets of actions are merged and duplicates removed
      if both switches have "exe or machine" action,
        the specified exe/machine overrides the file exe/machine
"""
  
  def check(self):
    if len(self.inlist) == 0:
      self.dir = 1
      self.file = "Make.py.last"
      self.labels = []
    else:
      self.dir = 0
      self.file = self.inlist[0]
      self.labels = self.inlist[1:]

  # read redo file
  # self.commands = list of commands to execute
      
  def setup(self):
    file = self.file
    if not os.path.isfile(file): error("Redo file %s does not exist" % file)
    lines = open(file,'r').readlines()
    
    cmdlines = []
    for line in lines:
      line = line.strip()
      if not line or line[0] == '#' : continue
      cmdlines.append(line)

    # if no labels, add all file commands to command list
    # if labels, make a dict with key = label, value = command
    #   and discard unlabeled commands
      
    dict = {}
    commands = []
    for line in cmdlines:
      words = line.split()
      if "-r" in words: error("Redo command cannot contain -r switch")
      if words[0][-1] == ':': label = words[0][:-1]
      else: label = None
      if not self.labels:
        if label: subprocess.append(' '.join(words[1:]))
        else: subprocess.append(line)
      else:
        if not label: continue
        dict[label] = ' '.join(words[1:])

    # extract labeled commands from dict and add to command list
        
    for label in self.labels:
      if label not in dict: error("Redo label not in redo file")
      subprocess.append(dict[label])

    self.commands = commands

# settings switch

class Settings(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
  
  def help(self):
    return """
-s set1 set2 ...
  possible settings = gzip #gzip ffmpeg #ffmpeg smallbig bigbig smallsmall exceptions #exceptions
  alter LAMMPS ifdef settings in Makefile.auto
    only happens if new Makefile.auto is created by use of "file" action
  gzip and #gzip turn on/off LAMMPS_GZIP setting
  ffmpeg and #ffmpeg turn on/off LAMMPS_FFMPEG setting
  smallbig, bigbig, smallsmall turn on LAMMPS_SMALLBIG, etc
    and turn off other two
  exceptions and #exceptions turn on/off LAMMPS_EXCEPTIONS setting
"""
  
  def check(self):
    if not self.inlist: error("-s args are invalid")
    for one in self.inlist:
      if one not in setargs: error("-s args are invalid")
  
# verbose switch

class Verbose(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
  
  def help(self):
    return """
-v (no arguments)
  produce verbose output as Make.py executes
  if -v not specified, minimal output is produced
"""
  
  def check(self):
    if len(self.inlist): error("-v args are invalid")

# zoutput switch for making copy of final Makefile.auto

class Zoutput(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)

  def help(self):
    return """
-z machine
  copy created/used src/MAKE/MINE/Makefile.auto to Makefile.machine in same dir
  copy created/used lib/*/Makefile.auto and lib/*/Makefile.lammps to
    Makefile_lib.machine and Makefile_lib_lammps.machine in same dir
  this can be used to preserve the machine Makefile and lib Makefiles
"""

  def check(self):
    if len(self.inlist) != 1: error("-z args are invalid")
    self.machine = self.inlist[0]

# ----------------------------------------------------------------
# lib classes, one per LAMMPS auxiliary lib
# ----------------------------------------------------------------

# ATC lib

class ATC(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "g++"
    self.lammpsflag = 0

  def help(self):
    return """
-atc make=suffix lammps=suffix2
  all args are optional and can be in any order
  make = use Makefile.suffix (def = g++)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-atc args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-atc args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-atc args are invalid")

  def build(self):
    libdir = dir.lib + "/atc"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)
    
    subprocess.check_output("cd %s; make -f Makefile.auto clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    if jmake: txt = "cd %s; make -j %d -f Makefile.auto" % (libdir,jmake.n)
    else: txt = "cd %s; make -f Makefile.auto" % libdir
    
    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/libatc.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/atc library")
    else: print("Created lib/atc library")
    
# AWPMD lib

class AWPMD(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "mpicc"
    self.lammpsflag = 0

  def help(self):
    return """
-awpmd make=suffix lammps=suffix2
  all args are optional and can be in any order
  make = use Makefile.suffix (def = mpicc)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-awpmd args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-awpmd args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-awpmd args are invalid")

  def build(self):
    libdir = dir.lib + "/awpmd"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)

    subprocess.check_output("cd %s; make -f Makefile.auto clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    if jmake: txt = "cd %s; make -j %d -f Makefile.auto" % (libdir,jmake.n)
    else: txt = "cd %s; make -f Makefile.auto" % libdir

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)
   
    if not os.path.isfile("%s/libawpmd.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/awpmd library")
    else: print("Created lib/awpmd library")

# COLVARS lib

class COLVARS(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "g++"
    self.lammpsflag = 0

  def help(self):
    return """
-colvars make=suffix lammps=suffix2
  all args are optional and can be in any order
  make = use Makefile.suffix (def = g++)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-colvars args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-colvars args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-colvars args are invalid")

  def build(self):
    libdir = dir.lib + "/colvars"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)

    subprocess.check_output("cd %s; make -f Makefile.auto clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    if jmake: txt = "cd %s; make -j %d -f Makefile.auto" % (libdir,jmake.n)
    else: txt = "cd %s; make -f Makefile.auto" % libdir

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/libcolvars.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/colvars library")
    else: print("Created lib/colvars library")

# CUDA lib

class CUDA(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.mode = "double"
    self.arch = "35"

  def help(self):
    return """
-cuda mode=double arch=35
  all args are optional and can be in any order
  mode = double or mixed or single (def = double)
  arch = M (def = 35)
    M = 31,35,37,etc for Kepler
    M = 20 for CC2.0 (GF100/110, e.g. C2050,GTX580,GTX470)
    M = 21 for CC2.1 (GF104/114,  e.g. GTX560, GTX460, GTX450)
    M = 13 for CC1.3 (GF200, e.g. C1060, GTX285)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-cuda args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-cuda args are invalid")
      if words[0] == "mode": self.mode = words[1]
      elif words[0] == "arch": self.arch = words[1]
      else: error("-cuda args are invalid")
    if self.mode != "double" and self.mode != "mixed" and \
          self.mode != "single":
      error("-cuda args are invalid")
    if not self.arch.isdigit(): error("-cuda args are invalid")
          
  def build(self): 
    libdir = dir.lib + "/cuda"
    subprocess.check_output("cd %s; make clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    if self.mode == "double": n = 2
    elif self.mode == "mixed": n = 3
    elif self.mode == "single": n = 1
    if jmake: txt = "cd %s; make -j %d precision=%d arch=%s" % \
          (libdir,jmake.n,n,self.arch)
    else: txt = "cd %s; make precision=%d arch=%s" % \
          (libdir,n,self.arch)

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/liblammpscuda.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/cuda library")
    else: print("Created lib/cuda library")

# GPU lib

class GPU(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "linux.double"
    self.lammpsflag = self.modeflag = self.archflag = self.homeflag = 0

  def help(self):
    return """
-gpu make=suffix lammps=suffix2 mode=double arch=N home=path
  all args are optional and can be in any order
  make = use Makefile.suffix (def = linux.double)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
  mode = double or mixed or single (def = CUDA_PREC in makefile)
  arch = 3x (x = digit for Kepler) or 2x (x = digit for Fermi)
         (def = CUDA_ARCH in makefile)
  home = path to Cuda, e.g. /usr/local/cuda (def = CUDA_HOME in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-gpu args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-gpu args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      elif words[0] == "mode":
        self.mode = words[1]
        self.modeflag = 1
      elif words[0] == "arch":
        self.arch = words[1]
        self.archflag = 1
      elif words[0] == "home":
        self.home = words[1]
        self.homeflag = 1
      else: error("-gpu args are invalid")
      if self.modeflag and (self.mode != "double" and
                            self.mode != "mixed" and
                            self.mode != "single"):
        error("-gpu args are invalid")
      if self.archflag and not self.arch.isdigit():
        error("-gpu args are invalid")

  def build(self):
    global gpubuildflag
    gpubuildflag = 1
    libdir = dir.lib + "/gpu"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.modeflag:
      if self.mode == "double":
        make.setvar("CUDA_PRECISION","-D_DOUBLE_DOUBLE")
      elif self.mode == "mixed":
        make.setvar("CUDA_PRECISION","-D_SINGLE_DOUBLE")
      elif self.mode == "single":
        make.setvar("CUDA_PRECISION","-D_SINGLE_SINGLE")
    if self.archflag:
      make.setvar("CUDA_ARCH","-arch=sm_%s" % self.arch)
    if self.homeflag:
      make.setvar("CUDA_HOME",self.home)
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)

    # special hack for shannon GPU cluster
    # must use "srun make" if on it, else just make
    # this is b/c Cuda libs are not all available on host

    make = "make"
    if "shannon" == platform.node(): make = "srun make"

    subprocess.check_output("cd %s; %s -f Makefile.auto clean" % (libdir,make),stderr=subprocess.STDOUT,shell=True)
    if jmake: txt = "cd %s; %s -j %d -f Makefile.auto" % (libdir,make,jmake.n)
    else: txt = "cd %s; %s -f Makefile.auto" % (libdir,make)

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/libgpu.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/gpu library")
    else: print("Created lib/gpu library")

# H5MD lib

class H5MD(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "h5cc"
    self.lammpsflag = 0

  def help(self):
    return """
-h5md make=suffix lammps=suffix2
  all args are optional and can be in any order
  make = use Makefile.suffix (def = h5cc)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-h5md args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-h5md args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-h5md args are invalid")

  def build(self):
    libdir = dir.lib + "/h5md"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)

    subprocess.check_output("cd %s; make clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    txt = "cd %s; make" % libdir

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/libch5md.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/h5md library")
    else: print("Created lib/h5md library")

# MEAM lib

class MEAM(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "gfortran"
    self.lammpsflag = 0

  def help(self):
    return """
-meam make=suffix lammps=suffix2
  all args are optional and can be in any order
  make = use Makefile.suffix (def = gfortran)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-meam args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-meam args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-meam args are invalid")

  def build(self):
    libdir = dir.lib + "/meam"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)

    subprocess.check_output("cd %s; make -f Makefile.auto clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    # do not use -j for MEAM build, parallel build does not work
    txt = "cd %s; make -f Makefile.auto" % libdir

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/libmeam.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/meam library")
    else: print("Created lib/meam library")

# POEMS lib

class POEMS(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "g++"
    self.lammpsflag = 0

  def help(self):
    return """
-poems make=suffix lammps=suffix2
  all args are optional and can be in any order
  make = use Makefile.suffix (def = g++)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-poems args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-poems args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-poems args are invalid")

  def build(self):
    libdir = dir.lib + "/poems"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)

    subprocess.check_output("cd %s; make -f Makefile.auto clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    if jmake: txt = "cd %s; make -j %d -f Makefile.auto" % (libdir,jmake.n)
    else: txt = "cd %s; make -f Makefile.auto" % libdir

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)

    if not os.path.isfile("%s/libpoems.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/poems library")
    else: print("Created lib/poems library")

# PYTHON lib

class PYTHON(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "g++"
    self.lammpsflag = 0

  def help(self):
    return """
-python lammps=suffix
  arg is optional, use Makefile.lammps if not specified
  lammps = use Makefile.lammps.suffix
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-python args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-python args are invalid")
      if words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-python args are invalid")

  def build(self):
    libdir = dir.lib + "/python"
    if self.lammpsflag:
      subprocess.check_output("cd %s; cp Makefile.lammps.%s Makefile.lammps" %
                         (libdir,self.lammps))
    if not os.path.isfile("%s/Makefile.lammps.%s" % (libdir,self.lammps)):
      error("Unsuccessful creation of lib/python/Makefile.lammps.%s file" % self.lammps)
    else: print("Created lib/python/Makefile.lammps file")

# QMMM lib

class QMMM(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.make = "gfortran"
    self.lammpsflag = 0

  def help(self):
    return """
-qmmm make=suffix lammps=suffix2
  all args are optional and can be in any order
  make = use Makefile.suffix (def = gfortran)
  lammps = use Makefile.lammps.suffix2 (def = EXTRAMAKE in makefile)
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-qmmm args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-qmmm args are invalid")
      if words[0] == "make": self.make = words[1]
      elif words[0] == "lammps": 
        self.lammps = words[1]
        self.lammpsflag = 1
      else: error("-qmmm args are invalid")

  def build(self):
    libdir = dir.lib + "/qmmm"
    make = MakeReader("%s/Makefile.%s" % (libdir,self.make))
    if self.lammpsflag:
      make.setvar("EXTRAMAKE","Makefile.lammps.%s" % self.lammps)
    make.write("%s/Makefile.auto" % libdir)

    subprocess.check_output("cd %s; make -f Makefile.auto clean" % libdir,stderr=subprocess.STDOUT,shell=True)
    if jmake: txt = "cd %s; make -j %d -f Makefile.auto" % (libdir,jmake.n)
    else: txt = "cd %s; make -f Makefile.auto" % libdir

    # if verbose, print output as build proceeds, else only print if fails

    if verbose: subprocess.call(txt,shell=True)
    else:
      try: subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      except Exception as e: print(e.output)
   
    if not os.path.isfile("%s/libqmmm.a" % libdir) or \
          not os.path.isfile("%s/Makefile.lammps" % libdir):
      error("Unsuccessful build of lib/qmmm library")
    else: print("Created lib/qmmm library")

# VORONOI lib

class VORONOI(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.install = ""
    
  def help(self):
    return """
-voronoi install="-d dir -v version -g -b -i installdir -l incdir libdir"
  arg is optional, only needed if want to run install.py script
  install = args to use with lib/voronoi/install.py script
    must enclose in quotes since install.py args have switches
    install.py can download, build, install, setup links to the Voro++ library
    see lib/voronoi/README for details on Voro++ and using install.py
"""

  def check(self):
    if self.inlist != None and len(self.inlist) == 0:
      error("-voronoi args are invalid")
    for one in self.inlist:
      words = one.split('=')
      if len(words) != 2: error("-voronoi args are invalid")
      if words[0] == "install": self.install = words[1]
      else: error("-voronoi args are invalid")

  def build(self):
    if not self.install: return
    libdir = dir.lib + "/voronoi"
    cmd = "cd %s; python install.py %s" % (libdir,self.install)
    txt = subprocess.check_output(cmd,stderr=subprocess.STDOUT,shell=True).decode()
    if verbose: print(txt)
    print("Created lib/voronoi library")

# ----------------------------------------------------------------
# build classes for intel, kokkos build options
# ----------------------------------------------------------------

# Intel class

class Intel(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.mode = "cpu"

  def help(self):
    return """
-intel mode
  mode = cpu or phi (def = cpu)
    build Intel package for CPU or Xeon Phi
"""

  def check(self):
    if self.inlist == None: return
    if len(self.inlist) != 1: error("-intel args are invalid")
    self.mode = self.inlist[0]
    if self.mode != "cpu" and self.mode != "phi":
      error("-intel args are invalid")

# Kokkos class

class Kokkos(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.mode = ""
    self.archgpu = None
    self.archcpu = None
    
  def help(self):
    return """
-kokkos mode archgpu=N archcpu=SNB
  mode is not optional, arch is optional
  mode = omp or cuda or phi (def = KOKKOS_DEVICES setting in Makefile )
    build Kokkos package for omp or cuda or phi
    sets KOKKOS_DEVICES to "OpenMP" (omp, phi) or "Cuda, OpenMP" (cuda)
  archgpu = number like 35 (Kepler) or 21 (Fermi) (def = none)
    sets KOKKOS_ARCH for GPU to appropriate value
  archcpu = SNB or HSW or BGQ or Power7 or Power8 (def = none)
    for CPU = SandyBridge, Haswell, BGQ, Power7, Power8
    sets KOKKOS_ARCH for GPU to appropriate value
"""

  def check(self):
    print(self.inlist)
    if self.inlist != None and len(self.inlist) == 0:
      error("-kokkos args are invalid")
      
    if self.inlist == None: return
    if len(self.inlist) < 1: error("-kokkos args are invalid")
    self.mode = self.inlist[0]
    if self.mode != "omp" and self.mode != "cuda" and self.mode != "phi":
      error("-kokkos args are invalid")
    for one in self.inlist[1:]:
      words = one.split('=')
      if len(words) != 2: error("-kokkos args are invalid")
      if words[0] == "archgpu": self.archgpu = words[1]
      elif words[0] == "archcpu": self.archcpu = words[1]
      else: error("-kokkos args are invalid")
      
# ----------------------------------------------------------------
# makefile classes for CC, FLAGS, MPI, JPG, PNG, FFT settings
# ----------------------------------------------------------------

# Cc class

class Cc(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.compiler = self.abbrev = ""
    self.wrap = ""
    self.parent = ""

  def help(self):
    return """
-cc compiler wrap=wcompiler,parent
  alter CC setting in Makefile.auto
    only happens if new Makefile.auto is created by use of "file" action
  compiler is required, all other args are optional
  compiler = any string with g++ or icc or icpc
             or mpi (or mpicxx, mpiCC, mpiicpc, etc)
    can be compiler name or full path to compiler
    mpi by itself is changed to mpicxx
  wcompiler = compiler for mpi wrapper to use
    use nvcc for building for Kokkos/cuda with provided nvcc_wrapper
  parent = openmpi or mpich
    parent style determines syntax for setting low-level compiler
"""

  def check(self):
    if len(self.inlist) < 1: error("-cc args are invalid")
    self.compiler = self.inlist[0]
    if self.compiler == "mpi":
      self.compiler = "mpicxx"
      self.abbrev = "mpi"
    elif self.compiler.startswith("mpi"):
      self.abbrev = "mpi"
    elif self.compiler == "g++" or self.compiler == "icc" or \
          self.compiler == "icpc":
      self.abbrev = self.compiler
    elif "mpi" in self.compiler: self.abbrev = "mpi"
    elif "g++" in self.compiler: self.abbrev = "g++"
    elif "icc" in self.compiler: self.abbrev = "icc"
    elif "icpc" in self.compiler: self.abbrev = "icpc"
    else: error("-cc args are invalid")
    for one in self.inlist[1:]:
      words = one.split('=')
      if len(words) != 2: error("-cc args are invalid")
      args = words[1].split(',')
      if len(args) != 2: error("-cc args are invalid")
      if words[0] == "wrap":
        if self.abbrev != "mpi": error("-cc compiler is not a wrapper")
        self.wrap = args[0]
        self.parent = args[1]
      else: error("-cc args are invalid")

# Flags class

class Flags(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.flags = []
    
  def help(self):
    return """
-flags var action N f1 f2 ... var action N f1 f2 ... 
  alter variable settings (flags) in Makefile.auto
    only happens if new Makefile.auto is created by use of "file" action
  var = CCFLAGS, LINKFLAGS, LIB, etc
    any variable in Makefile.auto, must already exist
  action = add or del
  N = # of flags to follow
  f1,f2,etc = flag to add or delete
    "-" char will be prepended to each flag
      for example: add 4 g O3 xHost "fp-model fast=2"
      will add: -g -O3 -xHost -fp-model fast=2
    for add: if flag already exists, no change is made
    for delete: flag of form "-O*", will delete any wildcard match
    for -O,-O2,-O3,etc: existing -O* will first be removed
"""

  def check(self):
    if len(self.inlist) < 1: error("-flags args are invalid")
    narg = len(self.inlist)
    i = 0
    while i < narg:
      if i+3 > narg: error("-flags args are invalid")
      var = self.inlist[i]
      action = self.inlist[i+1]
      if action != "add" and action != "del": error("-flags args are invalid")
      nflag = int(self.inlist[i+2])
      i += 3
      if i+nflag > narg: error("-flags args are invalid")
      flags = self.inlist[i:i+nflag]
      self.flags.append([var,action,flags])
      i += nflag
      
# Mpi class

class Mpi(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.style = self.dir = ""
                
  def help(self):
    return """
-mpi style dir=path
  alter MPI settings in Makefile.auto
    only happens if new Makefile.auto is created by use of "file" action
  style is required, all other args are optional
  style = mpi or mpich or ompi or serial
    mpi = no MPI settings (assume compiler is MPI wrapper)
    mpich = use explicit settings for MPICH
    ompi = use explicit settings for OpenMPI
    serial = use settings for src/STUBS library
  dir = path for MPICH or OpenMPI directory
    add -I and -L settings for include and lib sub-dirs
"""

  def check(self):
    if len(self.inlist) < 1: error("-mpi args are invalid")
    self.style = self.inlist[0]
    if self.style != "mpi" and self.style != "mpich" and \
      self.style != "ompi" and self.style != "serial":
      error("-mpi args are invalid")
    for one in self.inlist[1:]:
      words = one.split('=')
      if len(words) != 2: error("-mpi args are invalid")
      if words[0] == "dir": self.dir = words[1]
      else: error("-mpi args are invalid")

# Fft class

class Fft(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.dir = self.incdir = self.libdir = ""

  def help(self):
    return """
-fft mode lib=libname dir=homedir idir=incdir ldir=libdir
  alter FFT settings in Makefile.auto
    only happens if new Makefile.auto is created by use of "file" action
  mode is required, all other args are optional
  first removes all current FFT variable settings
  mode = none or fftw or fftw3 or ...
    adds -DFFT_MODE setting
  lib = name of FFT library to link with (def is libname = mode)
    adds -llib{libname} setting, e.g. -llibfftw3
  dir = home dir for include and library files (def = none)
    adds -Idir/include and -Ldir/lib settings
    if set, overrides idir and ldir args
  idir = dir for include file (def = none)
    adds -Iidir setting
  ldir = dir for library file (def = none)
    adds -Lldir setting
"""

  def check(self):
    if not len(self.inlist): error("-fft args are invalid")
    self.mode = self.inlist[0]
    self.lib = "-l%s" % self.mode
    for one in self.inlist[1:]:
      words = one.split('=')
      if len(words) != 2: error("-fft args are invalid")
      if words[0] == "lib": self.lib = "-l%s" % words[1]
      elif words[0] == "dir": self.dir = words[1]
      elif words[0] == "idir": self.incdir = words[1]
      elif words[0] == "ldir": self.libdir = words[1]
      else: error("-fft args are invalid")

# Jpg class

class Jpg(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.on = 1
    self.dir = self.incdir = self.libdir = ""

  def help(self):
    return """
-jpg flag dir=homedir idir=incdir ldir=libdir
  alter JPG settings in Makefile.auto
    only happens if new Makefile.auto is created by use of "file" action
  change JPG settings in makefile
  all args are optional, flag must come first if specified
  flag = yes or no (def = yes)
    include or exclude JPEG support
    adds/removes -DLAMMPS_JPEG and -ljpeg settings
  dir = home dir for include and library files (def = none)
    adds -Idir/include and -Ldir/lib settings
    if set, overrides idir and ldir args
  idir = dir for include file (def = none)
    adds -Iidir setting
  ldir = dir for library file (def = none)
    adds -Lldir setting
"""

  def check(self):
    for i,one in enumerate(self.inlist):
      if one == "no" and i == 0: self.on = 0
      elif one == "yes" and i == 0: self.on = 1
      else:
        words = one.split('=')
        if len(words) != 2: error("-jpeg args are invalid")
        if words[0] == "dir": self.dir = words[1]
        elif words[0] == "idir": self.incdir = words[1]
        elif words[0] == "ldir": self.libdir = words[1]
        else: error("-jpeg args are invalid")

# Png class

class Png(object):
  def __init__(self,list):
    self.inlist = copy.copy(list)
    self.on = 1
    self.dir = self.incdir = self.libdir = ""

  def help(self):
    return """
-png flag dir=homedir idir=incdir ldir=libdir
  alter PNG settings in Makefile.auto
    only happens if new Makefile.auto is created by use of "file" action
  all args are optional, flag must come first if specified
  flag = yes or no (def = yes)
    include or exclude PNG support
    adds/removes -DLAMMPS_PNG and -lpng settings
  dir = home dir for include and library files (def = none)
    adds -Idir/include and -Ldir/lib settings
    if set, overrides idir and ldir args
  idir = dir for include file (def = none)
    adds -Iidir setting
  ldir = dir for library file (def = none)
    adds -Lldir setting
"""

  def check(self):
    for i,one in enumerate(self.inlist):
      if one == "no" and i == 0: self.on = 0
      elif one == "yes" and i == 0: self.on = 1
      else:
        words = one.split('=')
        if len(words) != 2: error("-png args are invalid")
        if words[0] == "dir": self.dir = words[1]
        elif words[0] == "idir": self.incdir = words[1]
        elif words[0] == "ldir": self.libdir = words[1]
        else: error("-png args are invalid")

# ----------------------------------------------------------------
# auxiliary classes
# ----------------------------------------------------------------

# read, tweak, and write a Makefile

class MakeReader(object):

  # read a makefile
  # flag = 0 if file is full path name
  # flag = 1,2 if file is suffix for any Makefile.machine under src/MAKE
  #   look for this file in same order that src/Makefile does
  #   if flag = 1, read the file
  #   if flag = 2, just check if file exists

  def __init__(self,file,flag=0):
    if flag == 0:
      if not os.path.isfile(file): error("Makefile %s does not exist" % file)
      lines = open(file,'r').readlines()
    else:
      mfile = "%s/MAKE/MINE/Makefile.%s" % (dir.src,file)
      if not os.path.isfile(mfile):
        mfile = "%s/MAKE/Makefile.%s" % (dir.src,file)
        if not os.path.isfile(mfile):
          mfile = "%s/MAKE/OPTIONS/Makefile.%s" % (dir.src,file)
          if not os.path.isfile(mfile):
            mfile = "%s/MAKE/MACHINES/Makefile.%s" % (dir.src,file)
            if not os.path.isfile(mfile):
              error("Makefile.%s does not exist" % file)
      if flag == 1: lines = open(mfile,'r').readlines()
      else: return

    # scan lines of makefile
    # if not a variable line, just copy to newlines
    # if a variable line, concatenate any continuation lines
    # convert variable to var dict entry: key = name, value = list of words
    #   discard any portion of value string with a comment char
    # varinfo = list of variable info: (name, name with whitespace for print)
    # add index into varinfo to newlines
    # ccindex = index of "CC =" line, to add OMPI var before it
    # lmpindex = index of "LAMMPS-specific settings"
    #   line to add KOKKOS vars before it
    
    var = {}
    varinfo = []
    newlines = []
    pattern = "(\S+\s+=\s+)(.*)"
    conditional = 0
    multiline = 0
    self.ccindex = self.lmpindex = 0
    
    for line in lines:
      line = line[:-1]
      if "CC =" in line: self.ccindex = len(newlines)
      if "LAMMPS-specific settings" in line: self.lmpindex = len(newlines)
      if "ifeq" in line:
        conditional = 1
        continue
      if conditional:
        if "endif" in line:
          conditional = 0
        continue
      if multiline:
        if '#' in line: line = line[:line.find('#')]
        morevalues = line.split()
        values = values[:-1] + morevalues
        if values[-1] != '\\':
          var[name] = values
          multiline = 0
          newlines.append(str(len(varinfo)))
          varinfo.append((name,namewhite))
        continue
      varflag = 1
      if len(line.strip()) == 0: varflag = 0
      elif line.lstrip()[0] == '#': varflag = 0
      else:
        m = re.match(pattern,line)
        if not m: varflag = 0
      if varflag:
        namewhite = m.group(1)
        name = namewhite.split()[0]
        if name in var:
          error("Makefile variable %s appears more than once" % name)
        remainder = m.group(2)
        if '#' in remainder: remainder = remainder[:remainder.find('#')]
        values = remainder.split()
        if values and values[-1] == '\\': multiline = 1
        else:
          var[name] = values
          newlines.append(str(len(varinfo)))
          varinfo.append((name,namewhite))
      else:
        newlines.append(line)

    self.var = var
    self.varinfo = varinfo
    self.lines = newlines
             
  # return list of values associated with var
  # return None if var not defined
    
  def getvar(self,var):
    if var in self.var: return self.var[var]
    else: return None

  # set var to single value
  # if var not defined, error
  
  def setvar(self,var,value):
    if var not in self.var: error("Variable %s not in makefile" % var)
    self.var[var] = [value]
    
  # add value to var
  # do not add if value already defined by var
  # if var not defined,
  #   create new variable using "where"
  #   where="cc", line before "CC =" line, use ":="
  #   where="lmp", 2 lines before "LAMMPS-specific settings" line, use "="
  
  def addvar(self,var,value,where=""):
    if var in self.var:
      if value not in self.var[var]: self.var[var].append(value)
    else:
      if not where:
        error("Variable %s with value %s is not in makefile" % (var,value))
      if where == "cc":
        if not self.ccindex: error("No 'CC =' line in makefile to add variable")
        index = self.ccindex
        varwhite = "%s :=\t\t" % var
      elif where == "lmp":
        if not self.lmpindex: error("No 'LAMMPS-specific settings line' " +
                                    "in makefile to add variable")
        index = self.lmpindex - 2
        varwhite = "%s =\t\t" % var
      self.var[var] = [value]
      varwhite = "%s =\t\t" % var
      self.lines.insert(index,str(len(self.varinfo)))
      self.varinfo.append((var,varwhite))
      
  # if value = None, remove entire var
  #   no need to update lines or varinfo, write() will ignore deleted vars
  # else remove value from var
  # value can have trailing '*' to remove wildcard match
  # if var or value not defined, ignore it
      
  def delvar(self,var,value=None):
    #if var == "KOKKOS_DEVICES":
    #  print self.var,value
    if var not in self.var: return
    if not value:
      del self.var[var]
      #print "AGAIN",self.var
    elif value and value[-1] != '*':
      if value not in self.var[var]: return
      self.var[var].remove(value)
    else:
      value = value[:-1]
      values = self.var[var]
      dellist = []
      for i,one in enumerate(values):
        if one.startswith(value): dellist.append(i)
      while dellist: values.pop(dellist.pop())
      self.var[var] = values
      
  # write stored makefile lines to file, using vars that may have been updated
  # do not write var if not in dict, since has been deleted
  # wrap var values into multiple lines if needed
  # file = 1 if this is Makefile.auto, change 1st line to use "auto"
    
  def write(self,file,flag=0):
    fp = open(file,'w')
    for i,line in enumerate(self.lines):
      if not line.isdigit():
        if flag and i == 0:
          line = "# auto = makefile auto-generated by Make.py"
        print(line, file=fp)
      else:
        index = int(line)
        name = self.varinfo[index][0]
        txt = self.varinfo[index][1]
        if name not in self.var: continue
        values = self.var[name]
        print("%s%s" % (txt,' '.join(values)), file=fp)
  
# ----------------------------------------------------------------
# main program
# ----------------------------------------------------------------

# parse command-line args
# switches dict: key = switch letter, value = list of args
# switch_order = list of switches in order
# will possibly be merged with redo file args below
        
cmd_switches,cmd_switch_order = parse_args(sys.argv[1:])

if "v" in cmd_switches:
  # debug
  #print "Command-line parsing:"
  #for switch in cmd_switch_order:
  #  print "  %s: %s" % (switch,' '.join(cmd_switches[switch]))
  pass

# check for redo switch, process redo file
# redolist = list of commands to execute

redoflag = 0
redolist = []

if 'r' in cmd_switches and 'h' not in cmd_switches:
  redoflag = 1
  redo = Redo(cmd_switches['r'])
  redo.check()
  redo.setup()
  redolist = redo.commands
  redoindex = 0
  del redo
  if not redolist: error("No commands to execute from redo file")

# loop over Make.py commands
# if no redo switch, loop once for command-line command
# if redo, loop over one or more commands from redo file

while 1:
      
  # if redo:
  #   parse next command from redo file
  #   use command-line switches to add/replace file command switches
  #     do not add -r, since already processed
  #       and don't want -r swtich to appear in Make.py.last file
  #     if -a in both: concatenate, de-dup,
  #       specified exe/machine action replaces file exe/machine action
  #   print resulting new command
  # else just use command-line switches

  if redoflag:
    if redoindex == len(redolist): break
    args = redolist[redoindex].split()
    switches,switch_order = parse_args(args)
    redoindex += 1
    
    for switch in cmd_switches:
      if switch == 'r': continue
      if switch == 'a' and switch in switches:
        tmp = Actions(cmd_switches[switch] + switches[switch])
        tmp.dedup()
        switches[switch] = tmp.inlist
        continue
      if switch not in switches: switch_order.append(switch)
      switches[switch] = cmd_switches[switch]

    argstr = switch2str(switches,switch_order)
    print("Redo command: Make.py",argstr)
  else:
    switches = cmd_switches
    switch_order = cmd_switch_order

  # initialize all class variables to None

  for one in switchclasses: exec("%s = None" % one)
  for one in libclasses: exec("%s = None" % one)
  for one in buildclasses: exec("%s = None" % one)
  for one in makeclasses: exec("%s = None" % one)
  
  # classes = dictionary of created classes
  # key = switch, value = class instance

  classes = {}
  for switch in switches:
    if len(switch) == 1 and switch in abbrevs:
      i = abbrevs.index(switch)
      txt = '%s = classes["%s"] = %s(switches["%s"])' % \
          (switchclasses[i],switch,switchclasses[i].capitalize(),switch)
      exec(txt)
    elif switch in libclasses:
      i = libclasses.index(switch)
      txt = '%s = classes["%s"] = %s(switches["%s"])' % \
          (libclasses[i],switch,libclasses[i].upper(),switch)
      exec(txt)
    elif switch in buildclasses:
      i = buildclasses.index(switch)
      txt = '%s = classes["%s"] = %s(switches["%s"])' % \
          (buildclasses[i],switch,buildclasses[i].capitalize(),switch)
      exec(txt)
    elif switch in makeclasses:
      i = makeclasses.index(switch)
      txt = '%s = classes["%s"] = %s(switches["%s"])' % \
          (makeclasses[i],switch,makeclasses[i].capitalize(),switch)
      exec(txt)
    else: error("Unknown command-line switch -%s" % switch)

  # print help messages and exit

  if help or (actions and "-h" in actions.inlist) or not switches:
    if not help: help = Help(None)
    print(help.help())
    for switch in switch_order:
      if switch == "h": continue
      print(classes[switch].help()[1:])
    sys.exit()

  # create needed default classes if not specified with switch
  # dir and packages plus lib and build classes so defaults are set

  if not dir: dir = Dir(None)
  if not packages: packages = Packages(None)

  for one in libclasses:
    txt = "if not %s: %s = %s(None)" % (one,one,one.upper())
    exec(txt)

  for one in buildclasses:
    txt = "if not %s: %s = %s(None)" % (one,one,one.capitalize())
    exec(txt)

  # error check on args for all classes

  for switch in classes: classes[switch].check()

  # prep for action
  # actions.setup() detects if last action = machine
  # if yes, induce addition of "-m" and "-o" switches
  
  dir.setup()
  packages.setup()

  if actions:
    machine = actions.setup()
    if machine:
      switches['a'][-1] = "exe"
      if 'm' not in switches:
        switches['m'] = [machine]
        switch_order.insert(-1,'m')
        makefile = classes['m'] = Makefile(switches['m'])
        makefile.check()
      if 'o' not in switches:
        switches['o'] = [machine]
        switch_order.insert(-1,'o')
        output = classes['o'] = Output(switches['o'])
        output.check()

  # perform actions

  packages.install()

  if actions:
    for action in actions.alist:
      print("Action %s ..." % action)
      if action.startswith("lib-"): actions.lib(action[4:])
      elif action == "file": actions.file("file")
      elif action == "clean": actions.clean()
      elif action == "exe": actions.exe()

  packages.uninstall()
  
  # create copy of executable if requested, and exe action performed

  if output and actions and "exe" in actions.alist:
    txt = "cp %s/lmp_auto %s/lmp_%s" % (dir.src,dir.cwd,output.machine)
    subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
    print("Created lmp_%s in %s" % (output.machine,dir.cwd))

  # create copy of Makefile.auto if requested, and file or exe action performed
  # ditto for library Makefile.auto and Makefile.lammps files

  if zoutput and actions and \
        ("file" in actions.alist or "exe" in actions.alist):
    txt = "cp %s/MAKE/MINE/Makefile.auto %s/MAKE/MINE/Makefile.%s" % \
        (dir.src,dir.src,zoutput.machine)
    subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
    print("Created Makefile.%s in %s/MAKE/MINE" % (zoutput.machine,dir.src))
    if gpubuildflag:
      txt = "cp %s/gpu/Makefile.auto %s/MAKE/MINE/Makefile_gpu.%s" % \
          (dir.lib,dir.src,zoutput.machine)
      subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      print("Created Makefile_gpu.%s in %s/MAKE/MINE" % \
          (zoutput.machine,dir.src))
      txt = "cp %s/gpu/Makefile.lammps %s/MAKE/MINE/Makefile_gpu_lammps.%s" % \
          (dir.lib,dir.src,zoutput.machine)
      subprocess.check_output(txt,stderr=subprocess.STDOUT,shell=True)
      print("Created Makefile_gpu_lammps.%s in %s/MAKE/MINE" % \
          (zoutput.machine,dir.src))
      
  # write current Make.py command to src/Make.py.last

  fp = open("%s/Make.py.last" % dir.src,'w')
  print("# last invoked Make.py command", file=fp)
  print(switch2str(switches,switch_order), file=fp)
  fp.close()
  
  # if not redoflag, done

  if not redoflag: break
