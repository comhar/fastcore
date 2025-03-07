# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/06_docments.ipynb.

# %% ../nbs/06_docments.ipynb 2
from __future__ import annotations

import re
from tokenize import tokenize,COMMENT
from ast import parse,FunctionDef,AsyncFunctionDef,AnnAssign
from io import BytesIO
from textwrap import dedent
from types import SimpleNamespace
from inspect import getsource,isfunction,ismethod,isclass,signature,Parameter
from dataclasses import dataclass, is_dataclass
from .utils import *
from .meta import delegates
from . import docscrape
from inspect import isclass,getdoc

# %% auto 0
__all__ = ['empty', 'docstring', 'parse_docstring', 'isdataclass', 'get_dataclass_source', 'get_source', 'get_name', 'qual_name',
           'docments']

# %% ../nbs/06_docments.ipynb
def docstring(sym):
    "Get docstring for `sym` for functions ad classes"
    if isinstance(sym, str): return sym
    res = getdoc(sym)
    if not res and isclass(sym): res = getdoc(sym.__init__)
    return res or ""

# %% ../nbs/06_docments.ipynb
def parse_docstring(sym):
    "Parse a numpy-style docstring in `sym`"
    docs = docstring(sym)
    return AttrDict(**docscrape.NumpyDocString(docstring(sym)))

# %% ../nbs/06_docments.ipynb
def isdataclass(s):
    "Check if `s` is a dataclass but not a dataclass' instance"
    return is_dataclass(s) and isclass(s)

# %% ../nbs/06_docments.ipynb
def get_dataclass_source(s):
    "Get source code for dataclass `s`"
    return getsource(s) if not getattr(s, "__module__") == '__main__' else ""

# %% ../nbs/06_docments.ipynb
def get_source(s):
    "Get source code for string, function object or dataclass `s`"
    return getsource(s) if isfunction(s) or ismethod(s) else get_dataclass_source(s) if isdataclass(s) else s

# %% ../nbs/06_docments.ipynb
def _parses(s):
    "Parse Python code in string, function object or dataclass `s`"
    return parse(dedent(get_source(s)))

def _tokens(s):
    "Tokenize Python code in string or function object `s`"
    s = get_source(s)
    return tokenize(BytesIO(s.encode('utf-8')).readline)

_clean_re = re.compile(r'^\s*#(.*)\s*$')
def _clean_comment(s):
    res = _clean_re.findall(s)
    return res[0] if res else None

def _param_locs(s, returns=True):
    "`dict` of parameter line numbers to names"
    body = _parses(s).body
    if len(body)==1: #or not isinstance(body[0], FunctionDef): return None
        defn = body[0]
        if isinstance(defn, (FunctionDef, AsyncFunctionDef)):
            res = {arg.lineno:arg.arg for arg in defn.args.args}
            if returns and defn.returns: res[defn.returns.lineno] = 'return'
            return res
        elif isdataclass(s):
            res = {arg.lineno:arg.target.id for arg in defn.body if isinstance(arg, AnnAssign)}
            return res
    return None

# %% ../nbs/06_docments.ipynb
empty = Parameter.empty

# %% ../nbs/06_docments.ipynb
def _get_comment(line, arg, comments, parms):
    if line in comments: return comments[line].strip()
    line -= 1
    res = []
    while line and line in comments and line not in parms:
        res.append(comments[line])
        line -= 1
    return dedent('\n'.join(reversed(res))) if res else None

def _get_full(anno, name, default, docs):
    if anno==empty and default!=empty: anno = type(default)
    return AttrDict(docment=docs.get(name), anno=anno, default=default)

# %% ../nbs/06_docments.ipynb
def _merge_doc(dm, npdoc):
    if not npdoc: return dm
    if not dm.anno or dm.anno==empty: dm.anno = npdoc.type
    if not dm.docment: dm.docment = '\n'.join(npdoc.desc)
    return dm

def _merge_docs(dms, npdocs):
    npparams = npdocs['Parameters']
    params = {nm:_merge_doc(dm,npparams.get(nm,None)) for nm,dm in dms.items()}
    if 'return' in dms: params['return'] = _merge_doc(dms['return'], npdocs['Returns'])
    return params

# %% ../nbs/06_docments.ipynb
def _get_property_name(p):
    "Get the name of property `p`"
    if hasattr(p, 'fget'):
        return p.fget.func.__qualname__ if hasattr(p.fget, 'func') else p.fget.__qualname__
    else: return next(iter(re.findall(r'\'(.*)\'', str(p)))).split('.')[-1]

# %% ../nbs/06_docments.ipynb
def get_name(obj):
    "Get the name of `obj`"
    if hasattr(obj, '__name__'):       return obj.__name__
    elif getattr(obj, '_name', False): return obj._name
    elif hasattr(obj,'__origin__'):    return str(obj.__origin__).split('.')[-1] #for types
    elif type(obj)==property:          return _get_property_name(obj)
    else:                              return str(obj).split('.')[-1]

# %% ../nbs/06_docments.ipynb
def qual_name(obj):
    "Get the qualified name of `obj`"
    if hasattr(obj,'__qualname__'): return obj.__qualname__
    if ismethod(obj):       return f"{get_name(obj.__self__)}.{get_name(fn)}"
    return get_name(obj)

# %% ../nbs/06_docments.ipynb
def _docments(s, returns=True, eval_str=False):
    "`dict` of parameter names to 'docment-style' comments in function or string `s`"
    nps = parse_docstring(s)
    if isclass(s) and not is_dataclass(s): s = s.__init__ # Constructor for a class
    comments = {o.start[0]:_clean_comment(o.string) for o in _tokens(s) if o.type==COMMENT}
    parms = _param_locs(s, returns=returns) or {}
    docs = {arg:_get_comment(line, arg, comments, parms) for line,arg in parms.items()}

    sig = signature_ex(s, True)
    res = {arg:_get_full(p.annotation, p.name, p.default, docs) for arg,p in sig.parameters.items()}
    if returns: res['return'] = _get_full(sig.return_annotation, 'return', empty, docs)
    res = _merge_docs(res, nps)
    if eval_str:
        hints = type_hints(s)
        for k,v in res.items():
            if k in hints: v['anno'] = hints.get(k)
    return res

# %% ../nbs/06_docments.ipynb
@delegates(_docments)
def docments(elt, full=False, **kwargs):
    "Generates a `docment`"
    r = {}
    params = set(signature(elt).parameters)
    params.add('return')

    def _update_docments(f, r):
        if hasattr(f, '__delwrap__'): _update_docments(f.__delwrap__, r)
        r.update({k:v for k,v in _docments(f, **kwargs).items() if k in params
                  and (v.get('docment', None) or not nested_idx(r, k, 'docment'))})

    _update_docments(elt, r)
    if not full: r = {k:v['docment'] for k,v in r.items()}
    return AttrDict(r)
