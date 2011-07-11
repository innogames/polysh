#!/bin/bash

# http://bugs.python.org/issue644744

python setup.py install -O1 --root="$RPM_BUILD_ROOT" --record=INSTALLED_FILES
# 'brp-compress' gzips the man pages without distutils knowing... fix this
sed -i -e 's@man/man\([[:digit:]]\)/\(.\+\.[[:digit:]]\)$@man/man\1/\2.gz@g' INSTALLED_FILES
# actually, it doesn't on all distributions so just compress unconditionally
# before brp-compress is run
find "$RPM_BUILD_ROOT" -type f -name polysh.1 -exec gzip '{}' \;
