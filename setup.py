#! /usr/bin/env python

from distutils.core import setup
import sys

import fuse_adfs

setup(
    name         = "fuse_adfs",
    description  = "A FUSE filesystem for ADFS disc images",
    
    author       = "David Boddie",
    author_email = "david@boddie.org.uk",
    license      = fuse_adfs.__license__,
    url          = "http://www.boddie.org.uk/david/Projects/Python/FUSE",
    version      = fuse_adfs.__version__,

    py_modules   = ["ADFSlib"],    
    scripts      = ["fuse_adfs.py", "fuse_setup.py"]
    )
