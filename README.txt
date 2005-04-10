=========
fuse_adfs
=========

:Author: David Boddie
:Date: 2005-04-10

.. contents::

Introduction
------------

The ``fuse_adfs`` module provides a Filesystem in Userspace (FUSE_) utility
for presenting the contents of ADFS floppy disc images as a mountable
filesystem on Linux, relying on the ``ADFSlib`` module for its image reading
facilities.

With this filesystem, disc images can be mounted in the same way as floppy
discs and CDROMs, and navigated at the shell or with a file manager. The
filesystem translates ADFS-style filenames to Unix-friendly ones and adds
suffixes to filenames to help applications recognize certain types of files.

Requirements
------------

This utility requires both FUSE_ and the `Python bindings package for FUSE`_.
At the current time, the Python bindings need to be obtained from the FUSE
CVS repository. To obtain them, open a shell and find a suitable directory to
put them. First, log in to the SourceForge CVS server::

  cvs -d:pserver:anonymous@cvs.sourceforge.net:/cvsroot/fuse login

The ``cvs`` tool will ask you for a password - just press Return. To retrieve
the files from the server and put them in a directory called ``python``,
type::

  cvs -z3 -d:pserver:anonymous@cvs.sourceforge.net:/cvsroot/fuse co -P python

The ``setup.py`` file in the ``python`` directory can be used in the normal
way. At the command line, type the following::

  cd python
  python setup.py build

As root, install the Python bindings with the following command::

  python setup.py install

The ``fuse_adfs`` utility can now be installed.

Installing fuse_adfs
--------------------

Enter the ``fuse-adfs`` directory and, as root, type::

  python setup.py install

Mounting an image
-----------------

Before the ``fuse_adfs.py`` script can be run, the kernel module that provides
the userspace support must be loaded. The ``fuse_setup.py`` script provided
can be run as root to load the ``fuse`` kernel module as required.

Alternatively, you can type the following as root::

  modprobe fuse

As a normal user, you can now mount an ADFS image with the ``fuse_adfs.py``
utility, using the following syntax::

  fuse_adfs.py <mount point> <image path>

If the mount point does not exist, a directory will be created for it,
otherwise an existing directory can be used instead. Note that, if the
directory is not empty, its contents will be inaccessible until after the
image has been unmounted - they will not be deleted.

When you have finished with the image, type::

  fusermount -u <mount point>

The ``fuse_adfs.py`` utility will remove the directory if it created it.

 .. _FUSE: http://fuse.sourceforge.net/
 .. _`Python bindings package for FUSE`:
    http://cvs.sourceforge.net/viewcvs.py/fuse/python/
