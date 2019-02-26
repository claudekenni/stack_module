# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import functools
import glob
import os
import posixpath
import logging


from jinja2 import FileSystemLoader, Environment

# Import Salt libs
from salt.ext import six
import salt.utils.data
import salt.utils.jinja
import salt.utils.yaml
from salt.defaults import DEFAULT_TARGET_DELIM


log = logging.getLogger(__name__)
strategies = ('overwrite', 'merge-first', 'merge-last', 'remove')

def get_stack(*args, **kwargs):
    config = __salt__['config.option']('stack')
    stack = {}
    stack_config_files = list(config)
    traverse = {
        'pillar': functools.partial(salt.utils.data.traverse_dict_and_list, __pillar__),
        'grains': functools.partial(salt.utils.data.traverse_dict_and_list, __grains__),
        'opts': functools.partial(salt.utils.data.traverse_dict_and_list, __opts__),
        }
    for matcher, matchs in six.iteritems(kwargs):
        t, matcher = matcher.split(':', 1)
        if t not in traverse:
            raise Exception('Unknown traverse option "{0}", '
                            'should be one of {1}'.format(t, traverse.keys()))
        cfgs = matchs.get(traverse[t](matcher, None), [])
        if not isinstance(cfgs, list):
            cfgs = [cfgs]
        stack_config_files += cfgs
    for cfg in stack_config_files:
        if not os.path.isfile(cfg):
            log.info(
                'Ignoring pillar stack cfg "%s": file does not exist', cfg)
            continue
        stack = _process_stack_cfg(cfg, stack, id, __pillar__, __grains__)
    return stack


def _to_unix_slashes(path):
    return posixpath.join(*path.split(os.sep))


def _process_stack_cfg(cfg, stack, minion_id, pillar, __grains__):
    log.debug('Config: %s', cfg)
    basedir, filename = os.path.split(cfg)
    jenv = Environment(loader=FileSystemLoader(basedir), extensions=['jinja2.ext.do', salt.utils.jinja.SerializerExtension])
    jenv.globals.update({
        "__opts__": __opts__,
        "__salt__": __salt__,
        "__grains__": __grains__,
        "__stack__": {
            'traverse': salt.utils.data.traverse_dict_and_list,
            'cfg_path': cfg,
            },
        "minion_id": minion_id,
        "pillar": pillar,
        })
    for item in _parse_stack_cfg(
            jenv.get_template(filename).render(stack=stack)):
        item = item.strip()
        if not item:
            continue  # silently ignore whitespace or empty lines
        paths = glob.glob(os.path.join(basedir, item))
        if not paths:
            log.info(
                'Ignoring pillar stack template "%s": can\'t find from root '
                'dir "%s"', item, basedir
            )
            continue
        for path in sorted(paths):
            log.debug('YAML: basedir=%s, path=%s', basedir, path)
            # FileSystemLoader always expects unix-style paths
            unix_path = _to_unix_slashes(os.path.relpath(path, basedir))
            obj = salt.utils.yaml.safe_load(jenv.get_template(unix_path).render(stack=stack, ymlpath=path))
            if not isinstance(obj, dict):
                log.info('Ignoring pillar stack template "%s": Can\'t parse '
                         'as a valid yaml dictionary', path)
                continue
            stack = _merge_dict(stack, obj)
    return stack


def _cleanup(obj):
    if obj:
        if isinstance(obj, dict):
            obj.pop('__', None)
            for k, v in six.iteritems(obj):
                obj[k] = _cleanup(v)
        elif isinstance(obj, list) and isinstance(obj[0], dict) \
                and '__' in obj[0]:
            del obj[0]
    return obj


def _merge_dict(stack, obj):
    strategy = obj.pop('__', 'merge-last')
    if strategy not in strategies:
        raise Exception('Unknown strategy "{0}", should be one of {1}'.format(
            strategy, strategies))
    if strategy == 'overwrite':
        return _cleanup(obj)
    else:
        for k, v in six.iteritems(obj):
            if strategy == 'remove':
                stack.pop(k, None)
                continue
            if k in stack:
                if strategy == 'merge-first':
                    # merge-first is same as merge-last but the other way round
                    # so let's switch stack[k] and v
                    stack_k = stack[k]
                    stack[k] = _cleanup(v)
                    v = stack_k
                if type(stack[k]) != type(v):
                    log.warning('Force overwrite, types differ: \'%s\' != \'%s\'', stack[k], v)
                    stack[k] = _cleanup(v)
                elif isinstance(v, dict):
                    stack[k] = _merge_dict(stack[k], v)
                elif isinstance(v, list):
                    stack[k] = _merge_list(stack[k], v)
                else:
                    stack[k] = v
            else:
                stack[k] = _cleanup(v)
        return stack


def _merge_list(stack, obj):
    strategy = 'merge-last'
    if obj and isinstance(obj[0], dict) and '__' in obj[0]:
        strategy = obj[0]['__']
        del obj[0]
    if strategy not in strategies:
        raise Exception('Unknown strategy "{0}", should be one of {1}'.format(
            strategy, strategies))
    if strategy == 'overwrite':
        return obj
    elif strategy == 'remove':
        return [item for item in stack if item not in obj]
    elif strategy == 'merge-first':
        return obj + stack
    else:
        return stack + obj


def _parse_stack_cfg(content):
    '''
    Allow top level cfg to be YAML
    '''
    try:
        obj = salt.utils.yaml.safe_load(content)
        if isinstance(obj, list):
            return obj
    except Exception as e:
        pass
    return content.splitlines()

def get(key, default='', delimiter=DEFAULT_TARGET_DELIM, ordered=True):
    if ordered is True:
        stack = get_stack()
    else:
        stack = salt.utils.json.loads(salt.utils.json.dumps(get_stack()))
    return salt.utils.data.traverse_dict_and_list(
        get_stack(),
        key,
        default,
        delimiter)

def items(sanitize=False):
    '''
    Return all of the minion's stack values
    CLI Example:
    .. code-block:: bash
        salt '*' stack.items
    Sanitized CLI Example:
    .. code-block:: bash
        salt '*' stack.items sanitize=True
    '''
    if salt.utils.data.is_true(sanitize):
        out = dict(get_stack())
        for key, func in six.iteritems(_SANITIZERS):
            if key in out:
                out[key] = func(out[key])
        return out
    else:
        return get_stack()

def item(*args, **kwargs):
    '''
    Return one or more stack keys
    CLI Example:
    .. code-block:: bash
        salt '*' stack.item key
        salt '*' stack.item key1 key2
    Sanitized CLI Example:
    .. code-block:: bash
        salt '*' stack.item key sanitize=True
    '''
    ret = {}
    default = kwargs.get('default', '')
    delimiter = kwargs.get('delimiter', DEFAULT_TARGET_DELIM)

    try:
        for arg in args:
            ret[arg] = salt.utils.data.traverse_dict_and_list(
                get_stack(),
                arg,
                default,
                delimiter)
    except KeyError:
        pass

    if salt.utils.data.is_true(kwargs.get('sanitize')):
        for arg, func in six.iteritems(_SANITIZERS):
            if arg in ret:
                ret[arg] = func(ret[arg])
    return ret

def ls():  # pylint: disable=C0103
    '''
    Return a list of all available stack top level keys
    CLI Example:
    .. code-block:: bash
        salt '*' stack.ls
    '''
    return sorted(get_stack())

def has_value(key):
    '''
    Determine whether a key exists in the stack dictionary.
    Given a stack dictionary that contains the following structure::
        {'pkg': {'apache': 'httpd'}}
    One would determine if the apache key in the pkg dict exists by::
        pkg:apache
    CLI Example:
    .. code-block:: bash
        salt '*' stack.has_value pkg:apache
    '''
    return salt.utils.data.traverse_dict_and_list(
        get_stack(),
        key,
        KeyError) is not KeyError

def equals(key, value):
    '''
    Used to make sure the minion's stack key/value matches.
    Returns ``True`` if matches otherwise ``False``.
    .. versionadded:: 2017.7.0
    CLI Example:
    .. code-block:: bash
        salt '*' stack.equals fqdn <expected_fqdn>
        salt '*' stack.equals systemd:version 219
    '''
    return six.text_type(value) == six.text_type(get(key))
