import sys, os, string, re, commands, types, py_compile

import SCons

# The following adds all SCons SConscript API to the globals of this module.
version = map(int,string.split(SCons.__version__,'.')[:3])
if version[0] == 1 or version[1] >= 97 or (version[1] == 96 and version[2] >= 90):
    from SCons.Script import *
else:  # old style
    import SCons.Script.SConscript
    globals().update(SCons.Script.SConscript.BuildDefaultGlobals())

# CONSTANTS -- DO NOT CHANGE
context_success = 1
context_failure = 0
py_success = 0 # user-defined
unix_failure = 1

# Make sure error messages stand out visually
def stderr_write(message):
    sys.stderr.write('\n  %s\n' % message)

def pycompile(target, source, env):
    "convert py to pyc "
    for i in range(0,len(source)):
        py_compile.compile(source[i].abspath,target[i].abspath)
    return py_success

Pycompile = Builder(action=pycompile)

toheader = re.compile(r'\n((?:\n[^\n]+)+)\n'                     
                      '\s*\/\*(\^|\<(?:[^>]|\>[^*]|\>\*[^/])*\>)\*\/')
kandr = re.compile(r'\s*\{?\s*$') # K&R style function definitions end with {

def header(target=None,source=None,env=None):
# generate a header file
    inp = open(str(source[0]),'r')
    text = string.join(inp.readlines(),'')
    inp.close()
    file = str(target[0])
    prefix = env.get('prefix','')
    define = prefix + string.translate(os.path.basename(file),
                                       string.maketrans('.','_'))
    out = open(file,'w')
    out.write('/* This file is automatically generated. DO NOT EDIT! */\n\n')
    out.write('#ifndef _' + define + '\n')
    out.write('#define _' + define + '\n\n')
    for extract in toheader.findall(text):
        if extract[1] == '^':
            out.write(extract[0]+'\n\n')
        else:
            function = kandr.sub('',extract[0])
            out.write(function+';\n')
            out.write('/*'+extract[1]+'*/\n\n')
    out.write('#endif\n')
    out.close()
    return py_success

Header = Builder (action = Action(header,varlist=['prefix']),
                  src_suffix='.c',suffix='.h')

include = re.compile(r'#include\s*\"([^\"]+)\.h\"')

# find dependencies for C 
def depends(env,list,file):
    filename = string.replace(env.File(file+'.c').abspath,'build/','',1)
    fd = open(filename,'r')
    for line in fd.readlines():
        for inc in include.findall(line):
            if inc not in list and inc[0] != '_':
                list.append(inc)
                depends(env,list,inc)
    fd.close()


include90 = re.compile(r'^[^!]*use\s+(\S+)')

# find dependencies for Fortran-90
def depends90(env,list,file):
    filename = string.replace(env.File(file+'.f90').abspath,'build/','',1)
    fd = open(filename,'r')
    for line in fd.readlines():
        for inc in include90.findall(line):
            if inc not in list and inc != 'rsf':
                list.append(inc)
                depends90(env,list,inc)
    fd.close()

def included(node,env,path):
    file = os.path.basename(str(node))
    file = re.sub('\.[^\.]+$','',file)
    contents = node.get_contents()
    includes = include.findall(contents)
    if file in includes:
        includes.remove(file)
    return map(lambda x: x + '.h',includes)

Include = Scanner(name='Include',function=included,skeys=['.c'])

plat = {'OS': 'unknown',
        'distro': 'unknown',
        'arch': 'unknown',
        'cpu': 'unknown'}
pkg = {}

def need_pkg(type,fatal=True):
    global pkg, plat
    mypkg = pkg[type].get(plat['distro'])
    if mypkg:
        stderr_write('Needed package: ' + mypkg)
    if fatal:
        sys.exit(unix_failure)


def check_all(context):

    # FDNSI = Failure Does Not Stop Installation
    identify_platform(context)
    cc  (context)
    ar  (context)
    libs(context)
    c99 (context) # FDNSI
    x11 (context) # FDNSI
    ppm (context) # FDNSI
    jpeg(context) # FDNSI
    opengl(context) # FDNSI
    blas(context) # FDNSI
    mpi (context) # FDNSI
    omp (context) # FDNSI
    api = api_options(context)
    if 'c++' in api:
        cxx(context)
    if 'f77' in api:
        f77(context)
    if 'f90' in api:
        f90(context)
    if 'matlab' in api:
        matlab(context)
    if 'octave' in api:
        octave(context)
    if 'python' in api:
        python(context)

def identify_platform(context):
    global plat
    context.Message("checking platform ... ")
    plat['OS'] = context.env.get('PLATFORM',sys.platform)

    # Check for distributions / OS versions
    try:
        from platform import architecture, uname
        plat['arch'] = architecture()[0]
        name = uname()[2].split('.')[-1]
        if plat['OS'] == 'linux' or plat['OS'] == 'posix':
            if name[:2] == 'fc':
                plat['distro'] = 'fedora'
            elif name[:2] == 'EL' or name[:2] == 'el':
                plat['distro'] = 'RedHat EL' # Redhat Enterprise
            elif name[-7:] == 'generic':
                plat['distro'] = 'generic' # Ubuntu
        elif plat['OS'] == 'sunos':
            if name[:2] == '10':
                plat['distro'] = '10' # Solaris 10
        elif plat['OS'] == 'darwin':
             plat['distro'] = uname()[2]
             plat['cpu'] = uname()[5] # i386 / powerpc
        elif plat['OS'] == 'irix':
             plat['distro'] = uname()[2]
        elif plat['OS'] == 'hp-ux' or plat['OS'] == 'hpux':
             plat['distro'] = uname()[2].split('.')[-2]
        del architecture, uname
    except: # "platform" not installed. Python < 2.3
        # For each OS with Python < 2.3, should use specific
        # commands through os.system to find distro/version
        # Not known if what follows works everywhere:
        plat_nm = os.uname()[4]
        if plat_nm == 'x86_64':
            plat['arch'] = '64bit'
        elif plat_nm == 'i686':
            plat['arch'] = '32bit'
    context.Result('%(OS)s [%(distro)s]' % plat)

pkg['gcc'] = {'fedora':'gcc'}
pkg['libc'] = {'fedora':'glibc',
               'generic':'libc6-dev'}

# A C compiler is needed by most Madagascar programs
# Failing this test stops the installation.
def cc(context):
    context.Message("checking for C compiler ... ")
    CC = context.env.get('CC',WhereIs('gcc'))
    if CC:
        context.Result(CC)
    else:
        context.Result(context_failure)
        need_pkg('gcc')
    text = '''
    int main(int argc,char* argv[]) {
    return 0;
    }\n'''

    context.Message("checking if %s works ... " % CC)
    res = context.TryLink(text,'.c')
    context.Result(res)
    if not res:
        need_pkg('libc')
    if string.rfind(CC,'gcc') >= 0:
        oldflag = context.env.get('CCFLAGS')
        for flag in ('-std=gnu99 -Wall -pedantic',
                     '-std=gnu9x -Wall -pedantic',
                     '-Wall -pedantic'):
            context.Message("checking if gcc accepts '%s' ... " % flag)
            context.env['CCFLAGS'] = oldflag + ' ' + flag
            res = context.TryCompile(text,'.c')
            context.Result(res)
            if res:
                break
        if not res:
            context.env['CCFLAGS'] = oldflag
        # large file support
        (status,lfs) = commands.getstatusoutput('getconf LFS_CFLAGS')
        if not status:
            oldflag = context.env.get('CCFLAGS')
            context.Message("checking if gcc accepts '%s' ... " % lfs)
            context.env['CCFLAGS'] = oldflag + ' ' + lfs
            res = context.TryCompile(text,'.c')
            context.Result(res)
            if not res:
                context.env['CCFLAGS'] = oldflag
	# if Mac OS X and fink installed, update CPPPATH and LIBPATH
	if plat['OS'] == 'darwin' and os.path.isdir('/sw'):
	    context.env['CPPPATH'] = context.env.get('CPPPATH',[]) + \
                                     ['/sw/include',]
	    context.env['LIBPATH'] = context.env.get('LIBPATH',[]) + \
                                     ['/sw/lib',]
            context.env['LINKFLAGS'] = context.env.get('LINKFLAGS','') + \
                                     ' -framework Accelerate'

    elif plat['OS'] == 'sunos':
        context.env['CCFLAGS'] = string.replace(context.env.get('CCFLAGS',''),
                                                '-O2','-xO2')

pkg['ar']={'fedora':'binutils'}

# Used for building libraries.
def ar(context):
    context.Message("checking for ar ... ")
    AR = context.env.get('AR',WhereIs('ar'))
    if AR:
        context.Result(AR)
        context.env['AR'] = AR
    else:
        context.Result(context_failure)
        need_pkg('ar')

pkg['libs'] = {'fedora':'glibc-headers',
               'cygwin':'sunrpc (Setup...Libs)'}

# Failing this check stops the installation.
def libs(context):
    context.Message("checking for libraries ... ")
    LIBS = context.env.get('LIBS','m')
    if type(LIBS) is not types.ListType:
        LIBS = string.split(LIBS)
    if plat['OS'] == 'sunos' or plat['OS'] == 'hp-ux' or plat['OS'] == 'hpux':
        LIBS.append('nsl')
    elif plat['OS'] == 'cygwin':
        LIBS.append('rpc')
    elif plat['OS'] == 'darwin':
        LIBS.append('mx')
    elif plat['OS'] == 'interix':
        LIBS.append('rpclib')
    text = '''
    #include <rpc/types.h>
    #include <rpc/xdr.h>
    int main(int argc,char* argv[]) {
    return 0;
    }\n'''

    res = context.TryLink(text,'.c')
    if res:
        context.Result(str(LIBS))
        context.env['LIBS'] = LIBS
    else:
        context.Result(context_failure)
        need_pkg('libs')

pkg['c99'] = {'fedora':'glibc-headers'}

# Complex number support according to ISO C99 standard
def c99(context):
    context.Message("checking complex support ... ")
    text = '''
    #include <complex.h>
    #include <math.h>
    int main(int argc,char* argv[]) {
    float complex c;
    float f;
    f = cabsf(ccosf(c));
    return (int) f;
    }\n'''

    res = context.TryLink(text,'.c')
    if res:
        context.Result(res)
    else:
        context.env['CCFLAGS'] = context.env.get('CCFLAGS','')+' -DNO_COMPLEX'
        context.Result(context_failure)
        need_pkg('c99', fatal=False)

# The two lists below only used in the x11 check
xinc = [
    '/usr/X11/include',
    '/usr/X11R6/include',
    '/usr/X11R5/include',
    '/usr/X11R4/include',
    '/usr/include/X11',
    '/usr/include/X11R6',
    '/usr/include/X11R5',
    '/usr/include/X11R4',
    '/usr/local/X11/include',
    '/usr/local/X11R6/include',
    '/usr/local/X11R5/include',
    '/usr/local/X11R4/include',
    '/usr/local/include/X11',
    '/usr/local/include/X11R6',
    '/usr/local/include/X11R5',
    '/usr/local/include/X11R4',
    '/usr/X386/include',
    '/usr/x386/include',
    '/usr/XFree86/include/X11',
    '/usr/include',
    '/usr/local/include',
    '/usr/unsupported/include',
    '/usr/athena/include',
    '/usr/local/x11r5/include',
    '/usr/lpp/Xamples/include',
    '/usr/openwin/include',
    '/usr/openwin/share/include'
    ]

xlib = [
    '/usr/X11/lib64',
    '/usr/X11/lib',
    '/usr/X11R6/lib64',
    '/usr/X11R6/lib',
    '/usr/X11R5/lib',
    '/usr/X11R4/lib',
    '/usr/lib/X11',
    '/usr/lib/X11R6',
    '/usr/lib/X11R5',
    '/usr/lib/X11R4',
    '/usr/local/X11/lib',
    '/usr/local/X11R6/lib',
    '/usr/local/X11R5/lib',
    '/usr/local/X11R4/lib',
    '/usr/local/lib/X11',
    '/usr/local/lib/X11R6',
    '/usr/local/lib/X11R5',
    '/usr/local/lib/X11R4',
    '/usr/X386/lib',
    '/usr/x386/lib',
    '/usr/XFree86/lib/X11',
    '/usr/lib',
    '/usr/local/lib',
    '/usr/unsupported/lib',
    '/usr/athena/lib',
    '/usr/local/x11r5/lib',
    '/usr/lpp/Xamples/lib',
    '/lib/usr/lib/X11',
    '/usr/openwin/lib',
    '/usr/openwin/share/lib'
    ]

pkg['xaw']={'fedora':'libXaw-devel',
            'generic':'libxaw7-dev'}

# If this check is failed
# you may not be able to display .vpl images on the screen
def x11(context):
    text = '''
    #include <X11/Intrinsic.h>
    #include <X11/Xaw/Label.h>
    int main(int argc,char* argv[]) {
    return 0;
    }\n'''

    context.Message("checking for X11 headers ... ")
    INC = context.env.get('XINC','')
    if type(INC) is not types.ListType:
        INC = string.split(INC)

    oldpath = context.env.get('CPPPATH',[])

    res = None
    for path in filter(lambda x:
                       os.path.isfile(os.path.join(x,'X11/Xaw/Label.h')),
                       INC+xinc):
        context.env['CPPPATH'] = oldpath + [path,] 
        res = context.TryCompile(text,'.c')

        if res:
            context.Result(path)
            context.env['XINC'] = [path,]
            break

    if not res:
        context.Result(context_failure)
        stderr_write('xtpen (for displaying .vpl images) will not be built.')
        need_pkg('xaw', fatal=False)
        context.env['XINC'] = None
        return

    context.Message("checking for X11 libraries ... ")
    LIB = context.env.get('XLIBPATH','')
    if type(LIB) is not types.ListType:
        LIB = string.split(LIB)

    oldlibpath = context.env.get('LIBPATH',[])
    oldlibs = context.env.get('LIBS',[])

    XLIBS = context.env.get('XLIBS')
    if XLIBS:
        if type(XLIBS) is not types.ListType:
            XLIBS = string.split(XLIBS)
    else:
        if  plat['OS'] == 'interix':
            XLIBS =  ['Xaw','Xt','Xmu','X11','Xext','SM','ICE']
        elif plat['OS'] == 'linux' or plat['OS'] == 'posix':
            XLIBS = ['Xaw','Xt']
        else:
            XLIBS = ['Xaw','Xt','X11']

    res = None
    for path in filter(os.path.isdir,LIB+xlib):
        context.env['LIBPATH'] = oldlibpath + [path,] 
        res = context.TryLink(text,'.c')

        if res:
            context.Result(path)
            context.env['XLIBPATH'] = [path,]
            context.env['XLIBS'] = XLIBS
            break
    if not res:
        context.Result(context_failure)
        context.env['XLIBPATH'] = None

    context.env['CPPPATH'] = oldpath
    context.env['LIBPATH'] = oldlibpath
    context.env['LIBS'] = oldlibs

pkg['netpbm'] = {'fedora':'netpbm-devel',
                 'generic':'libnetpbm10-dev',
                 'darwin':'netpbm (fink)',
                 'cygwin':'libnetpbm-devel (Setup...Devel)'}

def ppm(context):
    context.Message("checking for ppm ... ")
    LIBS = context.env.get('LIBS','m')
    if type(LIBS) is not types.ListType:
        LIBS = string.split(LIBS)
    text = '''
    #include <ppm.h>
    int main(int argc,char* argv[]) {
    return 0;
    }\n'''
    for ppm in [context.env.get('PPM','netpbm'),'netpbm.10']:
	LIBS.append(ppm)
	res = context.TryLink(text,'.c')
	
	if res:
	    context.Result(res)
	    context.env['PPM'] = ppm
	    break
	else:
	    LIBS.pop()

    if res:
        LIBS.pop()
    else:
        context.Result(context_failure)
        need_pkg('netpbm', fatal=False)
        context.env['PPM'] = None

pkg['jpeg'] = {'fedora':'libjpeg-devel',
               'generic':'libjpeg62-dev'}

# If this test is failed, no writing to jpeg files
def jpeg(context):
    context.Message("checking for jpeg ... ")
    LIBS = context.env.get('LIBS','m')
    if type(LIBS) is not types.ListType:
        LIBS = string.split(LIBS)
    jpeg = context.env.get('JPEG','jpeg')
    LIBS.append(jpeg)
    text = '''
    #include <stdio.h>
    #include <jpeglib.h>
    int main(int argc,char* argv[]) {
    return 0;
    }\n'''

    res = context.TryLink(text,'.c')
    if res:
        context.Result(res)
        context.env['JPEG'] = jpeg
    else:
        context.Result(context_failure)
        stderr_write('sfbyte2jpg will not be built.')
        need_pkg('jpeg', fatal=False)
        context.env['JPEG'] = None

    LIBS.pop()

pkg['opengl'] = {'generic':'mesa-libGL-devel',
                 'fedora': 'mesa-libGL-devel + freeglut + freeglut-devel'}

# If this test is failed, no opengl programs
def opengl(context):
    global plat
    context.Message("checking for OpenGL ... ")
    LIBS = context.env.get('LIBS','m')
    if type(LIBS) is not types.ListType:
        LIBS = string.split(LIBS)
    LINKFLAGS = context.env.get('LINKFLAGS','')
    
    if plat['OS'] == 'darwin':
        oglflags = ' -framework AGL -framework OpenGL -framework GLUT'
        context.env['LINKFLAGS'] = LINKFLAGS + oglflags
        ogl = []
    else:
        oglflags = None
        ogl = context.env.get('OPENGL')
        if type(ogl) is not types.ListType:
            ogl = string.split(ogl)
    context.env['LIBS'] = LIBS + ogl

    text = '''
    #ifdef __APPLE__
    #include <OpenGL/glu.h>
    #include <GLUT/glut.h>
    #else
    #include <GL/glu.h>
    #include <GL/glut.h>
    #endif
    int main(int argc,char* argv[]) {
    glutInit (&argc, argv);
    return 0;
    }\n'''

    res = context.TryLink(text,'.c')
    if res:
        context.Result(res)    
        context.env['OPENGL'] = ogl 
        context.env['OPENGLFLAGS'] = oglflags
    else:
        context.env['OPENGL'] = None 
        context.env['OPENGLFLAGS'] = None
        context.Result(context_failure)
        need_pkg('opengl', fatal=False)

    if res:
        glew(context,LIBS,ogl)

    context.env['LIBS'] = LIBS
    context.env['LINKFLAGS'] = LINKFLAGS

pkg['glew'] = {'generic':'libglew + libglew-dev',
               'fedora': 'glew + glew-devel'}

# If this test is failed, no GLEW programs
def glew(context,LIBS,ogl):
    context.Message("checking for GLEW ... ")

    text = '''
    #include <GL/glew.h>
    #ifdef __APPLE__
    #include <GLUT/glut.h>
    #else
    #include <GL/glut.h>
    #endif
    int main(int argc,char* argv[]) {
    GLenum err;
    glutInit(&argc, argv);
    err = glewInit();
    return 0;
    }\n'''

    GLEW = context.env.get('GLEW','GLEW')
    context.env['LIBS'] =  LIBS + [GLEW] + ogl 
        
    res = context.TryLink(text,'.c')

    if res:
        context.Result(res)
        context.env['GLEW'] = GLEW
    else:
        
        context.Result(context_failure)
        need_pkg('glew', fatal=False)

def blas(context):
    context.Message("checking for BLAS ... ")
    LIBS = context.env.get('LIBS','m')
    if type(LIBS) is not types.ListType:
        LIBS = string.split(LIBS)
    blas = context.env.get('BLAS','blas')
    LIBS.append(blas)
    text = '''
    #ifdef __APPLE__
    #include <vecLib/vBLAS.h>
    #else
    #include <cblas.h>
    #endif
    int main(int argc,char* argv[]) {
    float d, x[]={1.,2.,3.}, y[]={3.,2.,1.};
    d = cblas_sdot(3,x,1,y,1);
    return 0;
    }\n'''

    res = context.TryLink(text,'.c')
    if res:
        context.Result(res)
        context.env['LIBS'] = LIBS
        context.env['BLAS'] = blas
        if plat['OS'] == 'cygwin':
            context.env['ENV']['PATH'] = context.env['ENV']['PATH'] + \
                                         ':/lib/lapack'
    else:
        context.Result(context_failure)
        context.env['CCFLAGS'] = context.env.get('CCFLAGS','') + ' -DNO_BLAS'
        context.env['CXXFLAGS'] = context.env.get('CXXFLAGS','') + ' -DNO_BLAS'
        LIBS.pop()
        context.env['BLAS'] = None

pkg['mpi'] = {'fedora':'openmpi, openmpi-devel, openmpi-libs'}

def mpi(context):
    context.Message("checking for MPI ... ")
    mpicc = context.env.get('MPICC',WhereIs('mpicc'))
    if mpicc:
        context.Result(mpicc)
        context.Message("checking if %s works ... " % mpicc)
        # Try linking with mpicc instead of cc
        text = '''
        #include <mpi.h>
        int main(int argc,char* argv[]) {
        MPI_Init(&argc,&argv);
        MPI_Finalize();
        }\n'''
        cc = context.env.get('CC')
        context.env['CC'] = mpicc
        res = context.TryLink(text,'.c')
        context.env['CC'] = cc
    else: # mpicc not found
        context.Result(context_failure)
        res = None
    if res:
        context.Result(res)
        context.env['MPICC'] = mpicc
    else:
        context.Result(context_failure)
        need_pkg('mpi', fatal=False)
        context.env['MPICC'] = None

pkg['omp'] = {'fedora':'libgomp'}

def omp(context):
    context.Message("checking for OpenMP ... ")
    LIBS  = context.env.get('LIBS',[])
    CC    = context.env.get('CC','gcc')
    flags = context.env.get('CCFLAGS','')
    gcc = (string.rfind(CC,'gcc') >= 0)
    icc = (string.rfind(CC,'icc') >= 0)
    if gcc:
        LIBS.append('gomp')
        CCFLAGS = flags + ' -fopenmp'
    elif icc:
        LIBS.append('guide')
        LIBS.append('pthread')
        CCFLAGS = flags + ' -openmp -D_OPENMP'
    else:
        CCFLAGS = flags

    text = '''
    #include <omp.h>
    int main(void) {
    int nt;
#pragma omp parallel
{
    nt = omp_get_num_threads();
}
    return 0;
    }
    '''
    context.env['LIBS'] = LIBS
    context.env['CCFLAGS'] = CCFLAGS
    res = context.TryLink(text,'.c')
    if res:
        context.Result(res)
        context.env['OMP'] = True
    else:
        context.Result(context_failure)
        need_pkg('omp', fatal=False)
        if gcc:
            LIBS.pop()
        if icc:
            LIBS.pop()
            LIBS.pop()
        context.env['LIBS'] = LIBS
        context.env['CCFLAGS'] = flags
        context.env['OMP'] = False

def api_options(context):
    context.Message("checking API options ... ")
    api = context.env.get('API')
    if api:
        api = string.split(string.lower(api),',')
    else:
        api = []

    valid_api_options = ['','c++', 'fortran', 'f77', 'fortran-90',
                         'f90', 'python', 'matlab', 'octave']

    for option in api:
        if not option in valid_api_options:
            api.remove(option)

    # Make tests for fortrans in API easy
    for i in range(len(api)):
        if api[i] == 'fortran':
            api[i] = 'f77'
        elif api[i] == 'fortran-90':
            api[i] = 'f90'

    # Eliminate duplicates if user was redundant
    try: # sets module was introduced in Py 2.3
        import sets
        api = list(sets.Set(api))
        del sets
    except:
        pass # Not a big deal if this is not done

    # Improve output readability
    if api == ['']:
        context.Result('none')
    else:
        context.Result(str(api))
    context.env['API'] = api

    return api

pkg['c++'] = {'fedora':'gcc-c++',
              'generic':'g++'}

# For the C++ API
def cxx(context):
    context.Message("checking for C++ compiler ... ")
    CXX = context.env.get('CXX')
    if CXX:
        context.Result(CXX)
    else:
        context.Result(context_failure)
        need_pkg('c++')
    context.Message("checking if %s works ... " % CXX)
    text = '''
    #include <valarray>
    int main(int argc,char* argv[]) {
    return 0;
    }\n'''
    res = context.TryLink(text,'.cc')
    context.Result(res)
    if not res:
        del context.env['CXX']
        sys.exit(unix_failure)
    if CXX[-3:]=='g++':
        oldflag = context.env.get('CXXFLAGS')
        for flag in ['-Wall -pedantic']:
            context.Message("checking if g++ accepts '%s' ... " % flag)
            context.env['CXXFLAGS'] = oldflag + ' ' + flag
            res = context.TryCompile(text,'.cc')
            context.Result(res)
            if res:
                break
        if not res:
            context.env['CXXFLAGS'] = oldflag

# Used in checks for both f77 and f90
fortran = {'g77':'f2cFortran',
           'f77':'f2cFortran',
           'gfortran':'NAGf90Fortran',
           'gfc':'NAGf90Fortran',
           'f2c':'f2cFortran'}

pkg['f77'] = {'fedora':'gcc-gfortran',
              'generic':'g77'}

def f77(context):
    context.Message("checking for F77 compiler ... ")
    F77 = context.env.get('F77')
    if not F77:
        compilers = ['gfortran','g77','f77','f90','f95','xlf90','pgf90',
                     'ifort','ifc','pghpf','gfc']
        F77 = context.env.Detect(compilers)
        if not F77:
            for comp in compilers:
                F77 = WhereIs(comp)
                if F77:
                    break
        context.env['F77'] = F77
    if F77:
        context.Result(F77)
    else:
        context.Result(context_failure)
        need_pkg('f77')
    if os.path.basename(F77) == 'ifc' or os.path.basename(F77) == 'ifort':
        intel(context)
        context.env.Append(F77FLAGS=' -Vaxlib')
    text = '''      program Test
      stop
      end
      '''
    context.Message("checking if %s works ... " % F77)
    oldlink = context.env.get('LINK')
    context.env['LINK'] = F77
    res = context.TryLink(text,'.f')
    context.env['LINK'] = oldlink
    context.Result(res)
    if not res:
        del context.env['F77']
        sys.exit(unix_failure)
    F77base = os.path.basename(F77)
    if F77base[:3] == 'f77' and plat['OS'] == 'sunos':
        cfortran = 'sunFortran'
    else:
        cfortran = fortran.get(F77base,'NAGf90Fortran')
    context.env['CFORTRAN'] = cfortran 
    context.Message("checking %s type ... " % F77)
    context.Result(cfortran)

pkg['f90'] = {'fedora':'gcc-gfortran',
              'generic':'gfortran'}

def f90_write_autofile(extension,content):
    filename=os.path.join('api','f90','ptr_sz.'+extension)
    handle = open(filename,'w')
    handle.write(content)
    handle.close()

def f90_write_ptr_sz():
    'Tell poor Fortran whether platform is 32 or 64 bit'
    if plat['arch'] == '32bit':
        str_insert_f90 = '9'
        str_insert_c   = '32'
    elif plat['arch'] == '64bit':
        str_insert_f90 = '12'
        str_insert_c   = '64'
    msg = 'File created by config'
    f90_write_autofile('h',
        '/* %s */\n#define RSF%sBIT\n' % (msg,str_insert_c) )
    f90_write_autofile('f90',
        '! %s\ninteger, parameter :: PTRKIND=selected_int_kind(%s)\n' % (msg,str_insert_f90) )

def f90(context):
    context.Message("checking for F90 compiler ... ")
    F90 = context.env.get('F90')
    if not F90:
        compilers = ['gfortran','gfc','f90','f95','xlf90','pgf90',
                     'ifort','ifc','pghpf']
        F90 = context.env.Detect(compilers)
        if not F90:
            for comp in compilers:
                F90 = WhereIs(comp)
                if F90:
                    break
        context.env['F90'] = F90
    if F90:
        context.Result(F90)
    else:
        context.Result(context_failure)
        need_pkg('f90')
    if os.path.basename(F90) == 'ifc' or os.path.basename(F90) == 'ifort':
        intel(context)
        context.env.Append(F90FLAGS=' -Vaxlib')
    main = '''program Test
    end program Test
    '''
    module = '''module testf90
    end module testf90
    '''
    context.Message("checking if %s works ... " % F90)
    oldlink = context.env.get('LINK')
    context.env['LINK'] = F90
    res1 = context.TryCompile(module,'.f90')
    res2 = context.TryLink(main,'.f90')
    context.env['LINK'] = oldlink
    context.Result(res1 and res2)
    if not res1 or not res2:
        del context.env['F90']
        sys.exit(unix_failure)
    base = os.path.basename(F90)
    context.Message("checking %s type ... " % base)
    cfortran = fortran.get(base,'NAGf90Fortran')
    context.env['CFORTRAN90'] = cfortran
    context.Result(cfortran)
    context.Message("checking F90 module extension ... ")
    f90module = re.compile(r'(?:testf90|TESTF90)(\.\w+)$')
    suffix = ''
    here = os.getcwd()
    for file in os.listdir(here):
        gotit = f90module.match(file)
        if gotit:
            suffix = gotit.group(1)
            os.remove(file)
            break
    context.env['F90MODSUFFIX'] = suffix
    context.Result(suffix)
    f90_write_ptr_sz()

def matlab(context):
    context.Message("checking for Matlab ... ")
    matlab = WhereIs('matlab')
    if matlab:
        context.Result(matlab)
        RSFROOT_lib = os.path.join(context.env.get('RSFROOT'),'lib')
        MATLABPATH = os.environ.get('MATLABPATH')
        if MATLABPATH:
            MATLABPATH += ':' + RSFROOT_lib
        else:
            MATLABPATH = RSFROOT_lib
        context.env['MATLAB'] = 'MATLABPATH=%s %s ' \
                                '-nosplash -nojvm -nodesktop' %(MATLABPATH,
                                                                matlab)
    else:
        context.Result(context_failure)
        stderr_write('Please install Matlab.')
        context.env['MATLAB'] = None
        sys.exit(unix_failure)

    context.Message("checking for mex ... ")
    mex = WhereIs('mex')
    if mex:
        context.Result(mex)
        context.env['MEX'] = mex
    else:
        context.Result(context_failure)
        stderr_write('Please install mex.')
        context.env['MEX'] = None
        sys.exit(unix_failure)

    # See http://www.mathworks.com/access/helpdesk/help/techdoc/ref/mex.html
    if plat['OS'] == 'linux' or plat['OS'] == 'posix':
        if plat['arch'] == '32bit':
            suffix = 'glx'
        else:
            suffix = 'a64'
    elif plat['OS'] == 'sunos':
        suffix = 'sol'
    elif plat['OS'] == 'darwin':
        if plat['cpu'] == 'i386':
            suffix = 'maci'
        else:
            suffix = 'mac'
    else:
        suffix = 'glx'
    context.env['MEXSUFFIX'] = '.mex' + suffix

pkg['octave'] = {'fedora':'octave',
                 'generic':'octave'}

pkg['mkoctave'] = {'fedora':'octave-devel',
                   'generic':'octave-headers'}

def octave(context):
    context.Message("checking for Octave ... ")
    octave = WhereIs('octave')
    if octave:
        context.Result(octave)
        context.env['OCTAVE'] = octave
        context.Message("checking for mkoctfile ... ")
        mkoctfile = WhereIs('mkoctfile')
        if mkoctfile:
            context.Result(mkoctfile)
            context.env['MKOCTFILE'] = mkoctfile
        else:
            context.Result(context_failure)
            stderr_write('Please install mkoctfile.')
            need_pkg('mkoctfile')
    else: # octave not found
        context.Result(context_failure)
        stderr_write('Please install Octave.')
        need_pkg('octave')

pkg['swig'] = {'fedora':'swig',
               'generic':'swig'}
pkg['numpy'] = {'fedora':'numpy',
                'generic':'python-scipy, python-numpy-dev'}
pkg['scipy'] = {'fedora':'scipy'}

def python(context):
    context.Message("checking for SWIG ... ")
    if 'swig' in Environment().get('TOOLS'):
        context.Result( WhereIs('swig') )
    else:
        context.Result(context_failure)
        need_pkg('swig')

    context.Message("checking for numpy ... ")
    try:
        import numpy
        context.Result(context_success)
        context.env['PYMODULES'] = ['numpy']
    except:
        context.Result(context_failure)
        need_pkg('numpy')

    context.Message("checking for scipy ... ")
    try:
        import scipy
        context.Result(context_success)
        context.env.Append(PYMODULES='scipy')
    except:
        context.Result(context_failure)
        need_pkg('scipy', fatal=False)

    context.Message("checking for pyct ... ")
    try:
        import pyct
        context.Result(context_success)
        context.env.Append(PYMODULES='pyct')
    except:
        context.Result(context_failure)

def intel(context):
    '''Trying to fix weird intel setup.'''
    libdirs = string.split(os.environ.get('LD_LIBRARY_PATH',''),':')
    libs = filter (lambda x: re.search('intel',x) and os.path.isdir(x),
                   libdirs)
    context.env.Append(ENV={'LD_LIBRARY_PATH':string.join(libs,':')})
    for key in ('INTEL_FLEXLM_LICENSE','INTEL_LICENSE_FILE','IA32ROOT'):
        license = os.environ.get(key)
        if license:
            context.env.Append(ENV={key:license})

def options(opts):
    opts.Add('ENV','SCons environment')
    opts.Add('AR','Static library archiver')
    opts.Add('JPEG','The libjpeg library')
    opts.Add('OPENGL','OpenGL libraries','GL GLU glut')
    opts.Add('OPENGLFLAGS','Flags for linking OpenGL libraries')
    opts.Add('GLEW','GLEW library','GLEW')
    opts.Add('MPICC','MPI C compiler')
    opts.Add('OMP','OpenMP support')
    opts.Add('BLAS','The BLAS library')
    opts.Add('PPM','The netpbm library')
    opts.Add('CC','The C compiler')
    opts.Add('CCFLAGS','General options that are passed to the C compiler',
             '-O2')
    opts.Add('CPPPATH',
             'The list of directories that the C preprocessor will search')
    opts.Add('LIBPATH',
             'The list of directories that will be searched for libraries')
    opts.Add('LIBS',
             'The list of libraries that will be linked with executables')
    opts.Add('LINKFLAGS','General options that are passed to the linker')
    opts.Add('XLIBPATH','Location of X11 libraries')
    opts.Add('XLIBS','X11 libraries')
    opts.Add('XINC','Location of X11 headers')
    opts.Add('PROGPREFIX','The prefix used for executable file names','sf')
    opts.Add('API','Support for additional languages. Possible values: c++, fortran or f77, fortran-90 or f90, matlab, octave, python')
    opts.Add('CXX','The C++ compiler')
    opts.Add('CXXFLAGS','General options that are passed to the C++ compiler',
             '-O2')
    opts.Add('F77','The Fortran-77 compiler')
    opts.Add('F77FLAGS','General options that are passed to the F77 compiler',
             '-O2')
    opts.Add('CFORTRAN','Type of the Fortran-77 compiler (for cfortran.h)')
    opts.Add('F90','The Fortran-90 compiler')
    opts.Add('F90FLAGS','General options that are passed to the F90 compiler',
             '-O2')
    opts.Add('CFORTRAN90','Type of the Fortran-90 compiler (for cfortran.h)')
    opts.Add('F90MODSUFFIX','Suffix of Fortran-90 module interface files')
    opts.Add('MEXSUFFIX','Suffix for mex files')
    opts.Add('MEX','Matlab function compiler')
    opts.Add('MATLAB','Matlab interpreter')
    opts.Add('OCTAVE','Octave interpreter')
    opts.Add('MKOCTFILE','Octave function compiler')
    opts.Add('PYMODULES','List of Python modules available')

local_include = re.compile(r'\s*\#include\s*\"([^\"]+)')

def includes(list,file):
    global local_include
    fd = open(file,'r')
    for line in fd.readlines():
         match = local_include.match(line)
         if match:
             other = os.path.join(os.path.dirname(file),match.group(1))
             if not other in list:
                 includes(list,other)
    list.append(file)
    fd.close()

def merge(target=None,source=None,env=None):
    global local_include
    sources = map(str,source)
    incs = []
    for src in sources:
        if not src in incs:
            includes(incs,src)
    out = open(str(target[0]),'w')
    for src in incs:
        inp = open(src,'r')
        for line in inp.readlines():
            if not local_include.match(line):
                out.write(line)
        inp.close()
    out.close()
    return py_success

def docmerge(target=None,source=None,env=None):
    outfile = target[0].abspath
    out = open(outfile,'w')
    out.write('import rsfdoc\n\n')
    for src in map(str,source):
        inp = open(src,'r')
        for line in inp.readlines():
                out.write(line)
        inp.close()
    alias = env.get('alias',{})
    for prog in alias.keys():
        out.write("rsfdoc.progs['%s']=%s\n" % (prog,alias[prog]))
    out.close()
    py_compile.compile(outfile,outfile+'c')
    return py_success

def pycompile_emit(target, source, env):
    target.append(str(target[0])+'c')
    return target,source 

Docmerge = Builder(action=Action(docmerge,varlist=['alias']),
                   emitter=pycompile_emit)

def placeholder(target=None,source=None,env=None):
    filename = str(target[0])
    out = open(filename,'w')
    var = env.get('var')
    out.write('#!/usr/bin/env python\n')
    out.write('import sys\n\n')
    out.write('sys.stderr.write(\'\'\'\n%s is not installed.\n')
    out.write('Check $RSFROOT/lib/rsfconfig.py for ' + var)
    out.write('\nand reinstall if necessary.')
    package = env.get('package')
    if package:
        out.write('\nPossible missing packages: ' + package)
    out.write('\n\'\'\' % sys.argv[0])\nsys.exit(1)\n')
    out.close()
    os.chmod(filename,0775)
    return py_success

Place = Builder (action = Action(placeholder,varlist=['var','package']))
