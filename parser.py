import os
from lxml import etree


hpath = os.path.join(os.path.abspath('.'), "Headers")


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
    __slots__ = ['api', 'vendor', 'name', 'req']

    def __init__(self, api, vendor, name, req):
        self.api = api
        self.vendor = vendor
        self.name = name
        self.req = req


class Parser(object):
    def __init__(self, fname=None):
        self.fname = fname
        self.parser = etree.XMLParser(remove_comments=True)
        self.et = etree.parse(os.path.join("Registry", self.fname),
                              parser=self.parser)
        self.root = self.et.getroot()
        self.cmd_lst = None

    @staticmethod
    def create_ext_dirs(path, dirs):
        if os.path.isdir(path.upper()):
            for d in dirs:
                if not os.path.isdir(os.path.join(path.upper(), d)):
                    os.mkdir(os.path.join(path.upper(), d))

    @staticmethod
    def create_ext_files(api, dictObj):
        for k, v in dictObj.items():
            for e in v:
                if e.req and os.path.isdir(os.path.join(api.upper(), k)):
                    os.mknod(os.path.join(api.upper(), k, e.name + '.py'))

    @staticmethod
    def write_header(header, fileObj):
        with open(os.path.join(hpath, header), "r") as h:
            for l in h.readlines():
                fileObj.write(l)

    @staticmethod
    def write_commands(cmdDict, ftrDict, extDict, fileObj):
        flsts = [f.req for v in ftrDict.values() for f in v if len(f.req) > 0]
        elsts = [e.req for v in extDict.values() for e in v if len(e.req) > 0]
        cmdSet = set()
        map(cmdSet.update, flsts + elsts)
        for cmd in cmdDict.keys():
            if cmd in cmdSet:
                fileObj.write(cmdDict[cmd].__str__() + "\n")

    def get_types(self, api):
        types = {}
        for t in self.root.findall('types/type'):
            api_name = api if t.attrib.get('api') is None else t.attrib.get('api')
            if not t.attrib.get('name') and t.text is not None:
                typeObj = Types(api_name, None, t.text,
                                t.find('name').text,
                                t.find('name').tail)
                types.setdefault(api_name, []).append(typeObj)
            elif t.text is None and t.find('name') is not None:
                typeObj = Types(api_name, None, None,
                                t.find('name').text,
                                t.find('name').tail)
                types.setdefault(api_name, []).append(typeObj)
            else:
                types.setdefault("dummy", []).append(t.attrib.get('name'))
        return types

    def get_enums(self):
        enums = []
        for e in self.root.findall('enums'):
            for i in e.findall('enum'):
                enums.append(Enums(e.attrib.get('namespace'), i.attrib.get('name'), i.attrib.get('value')))
        return enums

    def gen_cons(self, api):
        nspace = {}
        with open(os.path.join(api.upper(), 'constants.py'), 'w+') as cons:
            cons.write("# Auto generated file!\n")
            for x in self.get_enums():
                nspace.setdefault(x.namespace, []).append(x.__str__())
            for k, v in nspace.items():
                cons.write('\n\nclass {}:\n'.format(k))
                for i in v:
                    if "(" not in i:
                        cons.write('\t{}'.format(i))

    def get_commands(self):
        cmds = {}
        for cmd in self.root.find('commands').iterfind('command'):
            protos = cmd.find('proto').itertext()
            ptype = ''.join([text for text in protos][:-1])
            pname = cmd.find('proto').find('name').text
            params = [''.join(param.itertext()) for param in cmd.iterfind('param')]
            cmds[pname] = Commands(ptype, pname, params)
        return cmds

    def get_feature(self, api=None, ver=None):
        features = {}
        for f in self.root.iterfind("feature"):
            ftr_api = f.get('api')
            api_name = f.get('name')
            api_no = f.get('number')
            req = [c.attrib.get('name') for c in f.findall('require/command')]
            if ftr_api == api and api_no <= ver:
                ftrclass = Feature(ftr_api, api_name, req)
                features.setdefault((ftr_api, api_name), []).append(ftrclass)
        return features

    def get_extension(self, api=None):
        ext = {}
        for e in self.root.findall("extensions/extension"):
            api_name = e.attrib.get('supported').split('|')
            if api and api in api_name:
                ext_vendor = e.attrib.get('name').split("_")[1]
                ext_name = '_'.join(e.attrib.get('name').split("_")[2:])
                ext_req = [(r.attrib.get('name')) for r in e.findall('require/command')]
                extclass = Extension(api, ext_vendor, ext_name, ext_req)
                ext.setdefault(ext_vendor, []).append(extclass)
        return ext

    def gen_def(self, api=None, ver=None):
        defpath = os.path.join(os.path.abspath('.'), "Defs")
        defname = api + "defs.py"
        deffile = os.path.join(defpath, defname)
        with open(deffile, "w+") as f:
            f.write("\n")
            f.write("DEF = '''\n")
            self.write_header("khronos.h", f)
            f.write("\n")
            if api and api in ['egl', 'glx']:
                self.write_header("xorg.h", f)
                f.write('\n')
                self.write_header("xorg_xcb.h", f)
                f.write("\n")
            if api == 'egl':
                self.write_header("eglx11platform.h", f)
                f.write("\n")
            typs = self.get_types(api)
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
                if "GLhandleARB" in typs['dummy']:
                    f.write("typedef unsigned int GLhandleARB;\n")
            f.write("\n")
            cmd = self.get_commands()
            ftr = self.get_feature(api=api, ver=ver)
            ext = self.get_extension(api=api)
            f.write("/* Generated Commands for " + api + " Version " + ver + ". */\n")
            self.write_commands(cmd, ftr, ext, f)
            f.write("'''\n")


if __name__ == '__main__':
    p = Parser(fname='gl.xml')
    p.gen_def('gl', '4.5')









