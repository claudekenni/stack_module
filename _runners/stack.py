# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import functools
import glob
import os
import posixpath
import logging

# Import Salt libs
from salt.ext import six
import salt.utils.data
import salt.utils.jinja
import salt.utils.yaml
import salt.config
import salt.loader

def update(tgt, tgt_type='glob', opts=None):
    '''
    This function will update the stack data on the minion
    '''
    ret = {}
    serializers = salt.loader.serializers(__opts__)
    client = salt.client.get_local_client(__opts__['conf_file'])

    minions = client.cmd(
        tgt,
        'cp.get_dir',
        tgt_type=tgt_type,
        timeout=5,
        arg = [
            'salt://stack_data/stack',
            '/etc/salt/'
        ]
    )

    return minions

