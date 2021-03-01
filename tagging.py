import yaml
import re
import logging

class RegTag:
    regs = {}
    parents = {}

    def __init__(self, f):
        self.traverse(yaml.safe_load(f))
    
    def traverse(self, tags, parents = []):
        for k,v in tags.items():
            self.parents[k] = parents
            if type(v) is str:
                if k in self.regs:
                    logging.error(f'Ambigious label {k}')
                self.regs[k] = re.compile(v)
            elif type(v) is dict:
                self.traverse(v, parents + [k])
    
    def belongs_to(self, a , b):
        return a == b or b in self.parents[a]

    def exists(self, tag):
        return tag in self.parents.keys()

    def tag(self, string):
        matched = None
        for label, reg in self.regs.items():
            if reg.match(string.replace(' ','')):
                if matched:
                    logging.error(f'Ambigious pattern {reg.pattern} matched {label} and {matched}')
                matched = label
        return matched