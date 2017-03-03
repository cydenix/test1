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
    __slots__ = ['api', 'ver', 'enums', 'req']

    def __init__(self, api, ver, enums, req):
        self.api = api
        self.ver = ver
        self.enums = enums
        self.req = req


class Extension(object):
    __slots__ = ['api', 'vendor', 'name', 'enums', 'req']

    def __init__(self, api, vendor, name, enums, req):
        self.api = api
        self.vendor = vendor
        self.name = name
        self.enums = enums
        self.req = req


class Parser(object):
    def __init__(self, fname=None, api=None, ver=None):
        self.fname = fname
        self.parser = etree.XMLParser(remove_comments=True)
        self.et = etree.parse(os.path.join("Registry", self.fname),
                              parser=self.parser)
        self.root = self.et.getroot()
        self.tdict = self.get_types(api)
        self.cdict = self.get_commands()
        self.fdict = self.get_feature(api, ver)
        self.edict = self.get_extension(api)
        self.endict = self.get_enums()

    @staticmethod
    def write_header(header, fileObj):
        with open(os.path.join(hpath, header), "r") as h:
            for l in h.readlines():
                fileObj.write(l)

    @staticmethod
    def write_commands(cmdDict, ftrDict, extDict, fileObj):
        cmdSet = set()
        flsts = [f.req for v in ftrDict.values() for f in v if len(f.req) > 0]
        if extDict is not None:
            elsts = [e.req for v in extDict.values() for e in v if len(e.req) > 0]
            map(cmdSet.update, flsts + elsts)
        else:
            map(cmdSet.update, flsts)
        for cmd in cmdDict.keys():
            if cmd in cmdSet:
                fileObj.write(cmdDict[cmd].__str__() + "\n")

    def get_types(self, api=None):
        types = {}
        for t in self.root.find('types').iterfind('type'):
            if self.fname != 'gl.xml':
                api_name = api
            else:
                api_name = 'gl' if t.get('api') is None else t.get('api')
            if not t.get('name'):
                typeObj = Types(api_name, None,
                                t.text, t.find('name').text,
                                t.find('name').tail)
                types.setdefault(api_name, []).append(typeObj)
            else:
                types.setdefault("dummy", []).append(t.get('name'))
        return types

    def get_enums(self):
        enums = []
        for e in self.root.findall('enums'):
            for i in e.findall('enum'):
                enums.append(Enums(e.attrib.get('namespace'), i.attrib.get('name'), i.attrib.get('value')))
        return enums

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
        if api == 'gles3':
            api = 'gles2'
        for f in self.root.iterfind("feature"):
            ftr_api = f.get('api')
            api_name = f.get('name')
            api_no = f.get('number')
            enums = [e.attrib.get('name') for e in f.findall('require/enum')]
            req = [c.attrib.get('name') for c in f.findall('require/command')]
            if ftr_api == api and api_no <= ver:
                ftrclass = Feature(ftr_api, api_name, enums, req)
                features.setdefault((ftr_api, api_name), []).append(ftrclass)
        return features

    def get_extension(self, api=None):
        ext = {}
        for e in self.root.findall("extensions/extension"):
            api_name = e.attrib.get('supported').split('|')
            if api == 'gles3':
                api = 'gles2'
            if api and api in api_name:
                ext_vendor = e.attrib.get('name').split("_")[1]
                ext_name = '_'.join(e.attrib.get('name').split("_")[2:])
                ext_enums = [en.attrib.get('name') for en in e.findall('require/enum')]
                ext_req = [(r.attrib.get('name')) for r in e.findall('require/command')]
                extclass = Extension(api, ext_vendor, ext_name, ext_enums, ext_req)
                ext.setdefault(ext_vendor, []).append(extclass)
        return ext


