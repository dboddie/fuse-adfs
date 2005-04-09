#! /usr/bin/env python

"""
fuse_adfs.py

A FUSE filesystem for ADFS disc images.

Copyright (C) 2005 David Boddie <david@boddie.org.uk>

This software is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of
the License, or (at your option) any later version.

This software is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public
License along with this library; see the file COPYING
If not, write to the Free Software Foundation, Inc.,
59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""

import os, struct, sys, time
from os.path import stat

from fuse import Fuse

import ADFSlib

__version__ = "0.10 (Sat 9th April 2005)"


# Find the number of centiseconds between 1900 and 1970.
between_epochs = ((365 * 70) + 17) * 24 * 360000L

def from_riscos_time(load, exec_):

    # RISC OS time is given as a five byte block containing the
    # number of centiseconds since 1900 (presumably 1st January 1900).
    
    value = struct.unpack("<Q", struct.pack("<IBxxx", exec_, load & 0xff))[0]
    
    # Convert the time to the time elapsed since the Epoch (assuming
    # 1970 for this value).
    centiseconds = value - between_epochs
    
    # Convert this to a value in seconds and return a time tuple.
    return int(centiseconds / 100)

class ADFS_Error(Exception):

    pass

class File:

    def __init__(self, name, data, load, exec_, length):
    
        self.name = name
        self.data = data
        self.load = load
        self.exec_ = exec_
        self.length = length
    
    def stat(self):
    
        d = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        d[stat.ST_MODE] = stat.S_IFREG | stat.S_IRUSR
        d[stat.ST_SIZE] = len(self.data)
        d[stat.ST_GID] = os.getgid()
        d[stat.ST_UID] = os.getuid()
        d[stat.ST_MTIME] = from_riscos_time(self.load, self.exec_)
        print d[stat.ST_MTIME]
        
        return d

class Directory:

    def __init__(self, name, objects):
    
        self.name = name
        self.objects = objects
    
    def stat(self):
    
        d = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        d[stat.ST_MODE] = stat.S_IFDIR | stat.S_IRUSR | stat.S_IXUSR
        d[stat.ST_GID] = os.getgid()
        d[stat.ST_UID] = os.getuid()
        
        return d
    
    def contents(self):
    
        objs = []
        for obj in self.objects:
        
            if type(obj[1]) != type([]):
            
                objs.append(File(*obj))
            
            else:
            
                objs.append(Directory(*obj))
        
        return objs

class ADFS(Fuse):

    def __init__(self, *args, **kwargs):
    
        path = kwargs.get("path", None)
        
        if path is None:
        
            raise ADFS_Error, "No path specified"
        
        Fuse.__init__(self, *args)
        
        try:
        
            self.adffile = open(path, "rb")
            self.adfsdisc = ADFSlib.ADFSdisc(self.adffile, verify = 1)
        
        except IOError:
        
            raise ADFS_Error
        
        except ADFSlib.ADFS_exception:
        
            self.adffile.close()
            raise ADFS_Error
    
    def getattr(self, path):
    
        obj = self.find_file_within_image(path)
        
        if obj is None:
        
            raise ADFS_Error, "getattr: no such path (%s)" % path
        
        return obj.stat()
    
    def readlink(self, path):
    
        raise ADFS_Error, "readlink: not supported"
    
    def getdir(self, path):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, File):
        
            raise ADFS_Error, "getdir: no such path (%s)" % path
        
        return map(lambda f: (f.name, 0), obj.contents())
    
    def unlink(self, path):
    
        raise ADFS_Error, "unlink: not supported"
    
    def rmdir(self, path):
    
        raise ADFS_Error, "rmdir: not supported"
    
    def symlink(self, path):
    
        raise ADFS_Error, "symlink: not supported"
    
    def rename(self, path):
    
        raise ADFS_Error, "rename: not supported"
    
    def link(self, path):
    
        raise ADFS_Error, "link: not supported"
    
    def chmod(self, path):
    
        raise ADFS_Error, "chmod: not supported"
    
    def chown(self, path):
    
        raise ADFS_Error, "chown: not supported"
    
    def truncate(self, path, size):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            raise ADFS_Error, "truncate: no such path (%s)" % path
        
        return obj.data[:size]
    
    def mknod(self, path):
    
        raise ADFS_Error, "mknod: not supported"
    
    def utime(self, path):
    
        raise ADFS_Error, "utime: not supported"
    
    def open(self, path, flags):
    
        if flags & (os.O_WRONLY | os.O_RDWR) != 0:
        
            raise ADFS_Error, "open: this filesystem is read-only"
        
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            raise ADFS_Error, "open: no such path (%s)" % path
        
        return 0
    
    def read(self, path, length, offset):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            raise ADFS_Error, "read: no such path (%s)" % path
        
        return obj.data[offset:offset+length]
    
    def write(self, path):
    
        raise ADFS_Error, "write: not supported"
    
    def release(self, path, flags):
    
        return 0
    
    def statfs(self):
    
        files = self.count_files()
        
        return (self.adfsdisc.sector_size,
                self.adfsdisc.ntracks * self.adfsdisc.nsectors,
                0, files, 0)
    
    def fsync(self, path, isfsyncfile):
    
        return 0
    
    def find_file_within_image(self, path, objs = None):
    
        if objs is None:
        
            objs = self.adfsdisc.files
        
        elements = path.split(u"/")
        
        # Remove any empty elements.
        elements = filter(lambda x: x != u"", elements)
        
        if elements == []:
        
            # Special case for root directory.
            return Directory(u"/", objs)
        
        for this_obj in objs:
        
            # Examine each object and compare its name to the next path
            # element.
            
            if type(this_obj[1]) != type([]):
            
                # A file is found. 
                obj_name = this_obj[0]
                
                if obj_name == elements[0]:
                
                    # A match between names.
                    
                    if len(elements) == 1:
                    
                        # This is the last path element; we have found the
                        # required file.
                        return File(*this_obj)
                    
                    else:
                    
                        # There are more elements to satisfy but we can
                        # descend no further.
                        return None
                
                elif self.adfsdisc.disc_type.find("adE") == -1 and \
                     elements[0] == obj_name + u".inf":
                
                    # Old style discs will have .inf files, too.
                    
                    if len(elements) == 1:
                    
                        # Construct a .inf file to return to the client.
                        file_data = "%s\t%X\t%X\t%X\n" % \
                            tuple(this_obj[:1] + this_obj[2:])
                        
                        new_obj = \
                        (
                            this_obj[0] + ".inf", file_data,
                            0, 0, len(file_data)
                        )
                        
                        return File(*new_obj)
                    
                    else:
                    
                        # There are more elements to satisfy but we can
                        # descend no further.
                        return None
            
            else:
            
                # A directory is found.
                obj_name = this_obj[0]
                
                if obj_name == elements[0]:
                
                    # A match between names.
                    
                    if len(elements) == 1:
                    
                        # This is the last path element; we have found the
                        # required file.
                        return Directory(*this_obj)
                    
                    else:
                    
                        # More path elements need to be satisfied; descend
                        # further.
                        return self.find_file_within_image(
                            u"/".join(elements[1:]), this_obj[1]
                            )
        
        # No matching objects were found.
        return None
    
    def count_files(self, root = None):
    
        number = 0
        
        if root is None:
        
            root = self.adfsdisc.files
        
        for obj in root:
        
            if type(obj[1]) != type([]):
            
                number = number + 1
            
            else:
            
                number = number + self.count_files(root = obj[1])
        
        return number


if __name__ == "__main__":

    if len(sys.argv) < 3:
    
        sys.stderr.write(
            "Usage: %s [fuse options] <mount point> <image>\n" % sys.argv[0]
            )
        sys.exit(1)

    server = ADFS(sys.argv[:-1], path = sys.argv[-1])
    server.multithreaded = 1
    server.main()
    
    sys.exit(0)
