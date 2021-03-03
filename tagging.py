import yaml
import re
import logging

class RegTag:
    regs = {}
    parents = {}
    children = {}

    def __init__(self, f):
        self.traverse(yaml.safe_load(f))
    
    def traverse(self, tags, parents = []):
        for k,v in tags.items():
            self.parents[k] = parents
            if len(parents) > 0:
                direct_parent = parents[-1]
                if direct_parent not in self.children:
                    self.children[direct_parent] = []
                self.children[direct_parent].append(k)                
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

    def childs(self, tag):
        return self.children[tag] if tag in self.children else [tag]

    def tags(self, string):
        matched = []
        for label, reg in self.regs.items():
            if reg.match(string.replace(' ','')):
                if matched:
                    logging.error(f'Ambigious pattern {reg.pattern} matched {label} and {matched}')
                matched = self.parents[label] + [label]
        return matched

    def expand_parents(self, tags):
        if len(tags) == 1:
            return self.parents[tags[0]] + tags
        else:
            return tags