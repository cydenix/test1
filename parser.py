import os
from lxml import etree
import requests

url = "https://cvs.khronos.org/svn/repos/ogl/trunk/doc/registry/public/api/"
dpath = os.path.join(os.path.abspath('.'), "Registry")
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
        if self.fname is not None:
            if not os.path.isfile(os.path.join(dpath, self.fname)):
                self.get_file()

            self.et = etree.parse(os.path.join(dpath, self.fname),
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
    def write_header(header, fileObj):
        with open(os.path.join(hpath, header), "r") as h:
            for l in h.readlines():
                fileObj.write(l)

    @staticmethod
    def write_commands(cmd_dict, dictObj, fileObj):
        for v in dictObj.values():
            for x in v:
                for cmd in cmd_dict.keys():
                    if cmd in x.req:
                        fileObj.write(cmd_dict[cmd].__str__() + '\n')

    def get_file(self):
        req = requests.get(url + self.fname, stream=True)
        print "Downloading ... % s" % (self.fname)
        with open(os.path.join(dpath, self.fname), 'wb') as f:
            f.write(req.raw.read())
        del req

    def get_types(self, api=None):
        types = {}
        for t in self.root.findall('types/type'):
            api_name = self.fname.split('.')[0] if t.attrib.get('api') is None else t.attrib.get('api')
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
        cmds = {}
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
            cmds[pname] = Commands(ptype, pname, params)
        return cmds

    def get_feature(self, api=None):
        features = {}
        for f in self.root.findall("feature"):
            api_name = f.attrib.get('api')
            if api and api == api_name:
                ftrclass = Feature(api, api_name, [(r.attrib.get('name')) for r in f.findall('require/command')])
                features.setdefault(api_name, []).append(ftrclass)
        return features

    def get_extension(self, api=None):
        ext_dir_list = []
        ext = {}
        for e in self.root.findall("extensions/extension"):
            api_name = e.attrib.get('supported').split('|')
            if api and api in api_name:
                ext_vendor = e.attrib.get('name').split("_")[1]
                ext_name = '_'.join(e.attrib.get('name').split("_")[2:])
                extclass = Extension(api, ext_vendor, ext_name, [(r.attrib.get('name')) for r in e.findall('require/command')])
                ext.setdefault(ext_vendor, []).append(extclass)
                if ext_vendor not in ext_dir_list:
                    ext_dir_list.append(ext_vendor)
        self.create_ext_dirs(api, ext_dir_list)
        return ext

    def gen_def(self, api=None):
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
            typs = self.get_types()
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
            ftr = self.get_feature(api=api)
            self.write_commands(cmd, ftr, f)
            ext = self.get_extension(api=api)
            self.write_commands(cmd, ext, f)
            f.write("'''\n")


if __name__ == '__main__':
    p = Parser(fname='glx.xml')
    p.gen_def('glx')

