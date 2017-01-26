import os
from lxml import etree
import requests
url = "https://cvs.khronos.org/svn/repos/ogl/trunk/doc/registry/public/api/"
#parser = etree.XMLParser(remove_comments=True)
#et = etree.parse("egl.xml", parser=parser)
#root = et.getroot()


class Types(object):
    __slots__ = ['api', 'requires', 'typedef', 'name', 'tail']

    def __init__(self, api=None, requires=None, typedef=None, name=None, tail=None):
        self.api = api
        self.requires = requires
        self.typedef = typedef
        self.name = name
        self.tail = tail

    def __str__(self):
        if self.typedef is not None:
            return '{}{}{}\n'.format(self.typedef, self.name, self.tail)
        else:
            return '{}{}\n'.format(self.name, self.tail)


class Enums(object):
    __slots__ = ['namespace', 'name', 'value']

    def __init__(self, namespace, name, value):
        self.namespace = namespace
        self.name = name
        self.value = value

    def __str__(self):
        return '{} = {}\n'.format(self.name, self.value)


class Commands(object):
    __slots__ = ['ptype', 'name', 'params']

    def __init__(self, ptype, name, params):
        self.ptype = ptype
        self.name = name
        self.params = params

    def __str__(self):
        cmd_str = ', '.join(self.params).join(("(", ")"))
        return '{} {}{};'.format(self.ptype, self.name, cmd_str)


class Feature(object):
    __slots__ = ['api', 'ver', 'req']

    def __init__(self, api, ver, req):
        self.api = api
        self.ver = ver
        self.req = req


class Extension(object):
    __slots__ = ['vendor','name', 'req']

    def __init__(self, vendor, name, req):
        self.vendor = vendor
        self.name = name
        self.req = req


class Parser(object):
    def __init__(self, fname=None):
        self.fname = fname
        self.parser = etree.XMLParser(remove_comments=True)
        if self.fname is not None:
            if not os.path.isfile(self.fname):
                self.get_file()

            self.et = etree.parse(self.fname, parser=self.parser)
            self.root = self.et.getroot()

    def get_file(self):
        req = requests.get(url + self.fname, stream=True)
        print "Downloading ... % s" %(self.fname)
        with open(self.fname, 'wb') as f:
            f.write(req.raw.read())
        del req

    def gen_types(self, api=None):
        types = {}
        for t in self.root.findall('types/type'):
            api_name = self.fname.split('.')[0] if t.attrib.get('api') is None else t.attrib.get('api')
            if not t.attrib.get('name') and t.text is not None:
                types.setdefault(api_name, []).append(Types(api=api_name,
                                                            requires=None,
                                                            typedef=t.text,
                                                            name=t.find('name').text,
                                                            tail=t.find('name').tail))
            elif t.text is None and t.find('name') is not None:
                types.setdefault(api_name, []).append(Types(api=api_name,
                                                            requires=None,
                                                            typedef=None,
                                                            name=t.find('name').text,
                                                            tail=t.find('name').tail))
            else:
                types.setdefault("dummy", []).append(t.attrib.get('name'))
        return types

    def get_enums(self):
        enums = []
        cdef = []
        for e in self.root.findall('enums'):
            for i in e.findall('enum'):
                enums.append(Enums(e.attrib.get('namespace'), i.attrib.get('name'), i.attrib.get('value')))
        return enums

    def gen_cons(self):
        nspace = {}
        with open(self.fname.split(".")[0] + '_constants.py', 'w+') as cons:
            for x in self.get_enums():
                nspace.setdefault(x.namespace, []).append(x.__str__())
            for k, v in nspace.items():
                cons.write('\n\nclass {}:\n'.format(k))
                for i in v:
                    if "(" not in i:
                        cons.write('\t{}'.format(i))

    def get_commands(self):
        pname = str()
        ptype = str()
        cmdlst = []
        for c in self.root.findall("commands/command"):
            params = []
            if len(c.getchildren()) < 2:
                params = ['void']
                pname = c.find('proto/name').text
                if c.find('proto/ptype') is not None:
                    ptype = c.find('proto/ptype').text + c.find('proto/ptype').tail
            else:
                for e in c.getchildren():
                    if e.tag == 'proto':
                        if e.find('ptype') is not None:
                            ptype = e.find('ptype').text + ' ' + e.find('ptype').tail
                            pname = e.find('name').text
                        else:
                            ptype = e.text
                            pname = e.find('name').text

                    if e.tag == 'param':
                        if e.find('ptype') is not None:
                            prtype = e.find('ptype').text + e.find('ptype').tail
                            prname = e.find('name').text
                        else:
                            prtype = e.text
                            prname = e.find('name').text
                        params.append(prtype + ' ' + prname)
            cmdlst.append(Commands(ptype, pname, params))
        return cmdlst

    def get_feature(self, api=None):
        flist = []
        for f in self.root.findall("feature"):
            if api and api == f.attrib.get('api'):
                flist.append(Feature(api, f.attrib.get('name'), [r for r in f]))
        return flist

    @staticmethod
    def create_ext_dirs(path, dirs):
        if os.path.isdir(path.upper()):
            for d in dirs:
                if not os.path.isdir(os.path.join(path.upper(), d)):
                    os.mkdir(os.path.join(path.upper(), d))


    def gen_extension(self, api=None):
        ext_dir_list = []
        ext = {}
        for e in self.root.findall("extensions/extension"):
            ext_vendor = e.attrib.get('name').split("_")[1]
            ext_name = '_'.join(e.attrib.get('name').split("_")[2:])
            extclass = Extension(ext_vendor, ext_name, [r for r in e.findall('require')])
            ext.setdefault(ext_vendor, []).append(extclass)
            #if os.path.exists(os.path.join(api.upper(), ext_vendor)):
            #    os.mknod(os.path.join(api.upper(), ext_vendor, ext_name + ".py"))
            if ext_vendor not in ext_dir_list:
                ext_dir_list.append(ext_vendor)
        self.create_ext_dirs(api, ext_dir_list)
        return ext
                
                    

    def khronos(self):
        khr_defs = ["typedef int32_t                khronos_int32_t;\n",
                    "typedef uint32_t               khronos_uint32_t;\n",
                    "typedef int64_t                khronos_int64_t;\n",
                    "typedef uint64_t               khronos_uint64_t;\n",
                    "typedef signed   char          khronos_int8_t;\n",
                    "typedef unsigned char          khronos_uint8_t;\n",
                    "typedef signed   short int     khronos_int16_t;\n",
                    "typedef unsigned short int     khronos_uint16_t;\n",
                    "typedef signed   long  int     khronos_intptr_t;\n",
                    "typedef unsigned long  int     khronos_uintptr_t;\n",
                    "typedef signed   long  int     khronos_ssize_t;\n",
                    "typedef unsigned long  int     khronos_usize_t;\n",
                    "typedef          float         khronos_float_t;\n",
                    "typedef khronos_uint64_t khronos_utime_nanoseconds_t;\n",
                    "typedef khronos_int64_t  khronos_stime_nanoseconds_t;\n"]
        return khr_defs

    def xorg(self):
        xorg_defs = ["typedef ... Display;\n",
                     "typedef int Bool;\n",
                     "typedef unsigned long XID;\n"
                     "typedef XID Font;\n",
                     "typedef XID Screen;\n",
                     "typedef XID Status;\n",
                     "typedef XID Window;\n",
                     "typedef XID Pixmap;\n",
                     "typedef XID XVisualInfo;\n",
                     "typedef XID Colormap;\n"]
        return xorg_defs

    def xorg_xcb(self):
        xorgxcb_defs = ["extern Display *XOpenDisplay(const char*);",
                        "xcb_connection_t *XGetXCBConnection(Display *dpy);",
                        "enum XEventQueueOwner { XlibOwnsEventQueue = 0, XCBOwnsEventQueue };",
                        "void XSetEventQueueOwner(Display *dpy, enum XEventQueueOwner owner);"]
        return xorgxcb_defs

    def gen_ffi(self, api=None):
        khr = self.khronos()
        with open(self.fname.split(".")[0] + "defs.py", "w+") as f:
            f.write("\n")
            f.write("DEF = '''\n")
            for k in khr:
                f.write(k)
            f.write("\n")
            if self.fname.split(".")[0] in ['egl', 'glx']:
                for x in self.xorg():
                    f.write(x)
                for xc in self.xorg_xcb():
                    f.write(xc + '\n')
            f.write("\n")
            if self.fname.split(".")[0] == 'egl':
                f.write("\n")
                f.write("typedef Display *EGLNativeDisplayType;\n")
                f.write("typedef Pixmap   EGLNativePixmapType;\n")
                f.write("typedef Window   EGLNativeWindowType;")
                f.write("typedef khronos_int32_t EGLint;\n")
                f.write("\n")
            typs = self.gen_types()
            if api and api in ['glsc2', 'gles1', 'gles2']:
                for t in typs['gl']:
                    for g in typs[api]:
                        if g.name == t.name:
                            typs['gl'].remove(t)
                for k, v in typs.items():
                    if k in ['gl', api]:
                        for x in v:
                            f.write(x.__str__())
            elif api and api == 'glx':
                for v in typs['dummy']:
                    if v[:2] in ['GL', 'VL', 'DM']:
                        f.write("typedef ... " + v + ";\n")
                f.write("\n")
                for v in typs[api]:
                    f.write(v.__str__())
            elif api:
                for v in typs[api]:
                    f.write(v.__str__())
            f.write("\n")
            cmd = self.get_commands()
            ftr = self.get_feature(api='glx')

            cmd_lst = []
            for futr in ftr:
                for rq in futr.req:
                    if rq.findall('command'):
                        for c in rq.findall('command'):
                            if c.attrib.get('name') not in cmd_lst:
                                cmd_lst.append(c.attrib.get('name'))
            for x in cmd_lst:
                for cm in cmd:
                    if cm.name == x:
                        f.write(cm.__str__() + "\n")

            f.write("'''\n")

if __name__ == '__main__':
    p = Parser(fname='glx.xml')
    p.gen_extension(api='glx')
