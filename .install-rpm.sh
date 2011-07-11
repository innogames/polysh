#!/bin/bash

# http://bugs.python.org/issue644744

python setup.py install -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

# 'brp-compress' gzips the man pages without distutils knowing... fix this
NEW_BASENAME="$(basename "$(find "$RPM_BUILD_ROOT" -type f -name "polysh.1*")")"
set "s/polysh.1/$NEW_BASENAME/g" -i INSTALLED_FILES
