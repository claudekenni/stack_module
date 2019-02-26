copy-stack:
  file.recurse: 
    - name: /etc/salt/stack
    - source: salt://{{tpldir}}/stack
    - clean: True
    - include_empty: True
