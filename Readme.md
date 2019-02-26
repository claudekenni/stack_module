Stack Module
===========
This is an Idea on how this Pillar Module could be used as an Execution Module.
The Config execution module has been adjusted to include the stack data within config.get.


Example
===========
Clone to formulas, add to file_roots and restart master

Sync Modules
```
lab08ld201:/srv/formulas/stack_mod # salt \* saltutil.sync_modules
lab08ld201:
    - modules.config
    - modules.stack
```

Sync Runner to master
```
lab08ld201:/srv/formulas/stack_mod # salt-run saltutil.sync_runners
- runners.stack
```

Update the stack data by executing the runner
```
lab08ld201:/srv/formulas/stack_mod # salt-run stack.update \*
lab08ld201:
    - /etc/salt/stack/common/common.yml
    - /etc/salt/stack/common/salt-minion.yml
    - /etc/salt/stack/core.yml
    - /etc/salt/stack/minions/.gitkeep
    - /etc/salt/stack/minions/minion.yml
    - /etc/salt/stack/osarchs/amd64.yml
    - /etc/salt/stack/oscodenames/xenial.yml
    - /etc/salt/stack/stack.cfg
```

Now we can use stack.get/ls/items/item the same way the pillar and grains execution module work
```
lab08ld201:/srv/formulas/stack_mod # salt-call stack.ls
local:
    - common
    - core
    - salt
lab08ld201:/srv/formulas/stack_mod # salt-call stack.item common
local:
    ----------
    common:
        True
lab08ld201:/srv/formulas/stack_mod # salt-call stack.items
local:
    ----------
    common:
        True
    core:
        Testvalue
    salt:
        ----------
        minion:
            ----------
            master:
                127.0.0.1
lab08ld201:/srv/formulas/stack_mod # salt-call stack.get salt:minion
local:
    ----------
    master:
        127.0.0.1
```

And by updating the config module we can use
```
lab08ld201:/srv/formulas/stack_mod # salt-call config.get core
local:
    Testvalue
```

```diff
lab08ld201:/srv/formulas/stack_mod # diff /usr/lib/python2.7/site-packages/salt/modules/config.py /var/cache/salt/minion/extmods/modules/config.py
216a217
>
218c219
<         omit_pillar=False, omit_master=False, omit_grains=False):
---
>         omit_pillar=False, omit_master=False, omit_stack=False, omit_grains=False):
384a386,394
>         if not omit_stack:
>             ret = salt.utils.data.traverse_dict_and_list(
>                 __salt__['stack.items'](),
>                 key,
>                 '_|-',
>                 delimiter=delimiter)
>             if ret != '_|-':
>                 return sdb.sdb_get(ret, __opts__)
>
401a412
>         data = salt.utils.dictupdate.merge(data, __salt__['stack.items'](), strategy=merge, merge_lists=merge_lists)
```
