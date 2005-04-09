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
        
        self.info_handlers = \
        {
            0xfca00:    self.squash_info,
            0xddc00:    self.nspark_info
        }
    
    def getattr(self, path):
    
        obj = self.find_file_within_image(path)
        
        if obj is None:
        
            return None
        
        return obj.stat()
    
    def readlink(self, path):
    
        # readlink is not supported
        return None
    
    def getdir(self, path):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, File):
        
            return None
        
        return map(lambda f: (self.encode_name_from_object(f), 0), obj.contents())
    
    def unlink(self, path):
    
        # unlink is not supported
        return None
    
    def rmdir(self, path):
    
        # rmdir is not supported
        return None
    
    def symlink(self, path):
    
        # symlink is not supported
        return None
    
    def rename(self, path):
    
        # rename is not supported
        return None
    
    def link(self, path):
    
        # link is not supported
        return None
    
    def chmod(self, path):
    
        # chmod is not supported
        return None
    
    def chown(self, path):
    
        # chown is not supported
        return None
    
    def truncate(self, path, size):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            return None
        
        return obj.data[:size]
    
    def mknod(self, path):
    
        # mknod is not supported
        return None
    
    def utime(self, path):
    
        # utime is not supported
        return None
    
    def open(self, path, flags):
    
        if flags & (os.O_WRONLY | os.O_RDWR) != 0:
        
            # This filesystem is read-only.
            return None
        
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            return None
        
        return 0
    
    def read(self, path, length, offset):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            return None
        
        return obj.data[offset:offset+length]
    
    def write(self, path):
    
        # write is not supported
        return None
    
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
        
        elements = path.split("/")
        
        # Remove any empty elements.
        elements = filter(lambda x: x != "", elements)
        
        if elements == []:
        
            # Special case for root directory.
            return Directory("/", objs)
        
        for this_obj in objs:
        
            # Examine each object and compare its name to the next path
            # element.
            
            if type(this_obj[1]) != type([]):
            
                # A file is found. 
                obj_name = self.encode_name_from_entry(this_obj)
                
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
                     elements[0] == obj_name + ".inf":
                
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
                obj_name = self.encode_name_from_entry(this_obj)
                
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
                            "/".join(elements[1:]), this_obj[1]
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
    
    def encode_name_from_object(self, obj):
    
        if isinstance(obj, File):
        
            return self.encode_name_from_entry(
                (obj.name, obj.data, obj.load, obj.exec_, obj.length)
                )
        
        else:
        
            return ".".join(obj.name.split("/"))
    
    def encode_name_from_entry(self, obj):
    
        name = obj[0]
        
        # If the name contains a slash then replace it with a dot.
        new_name = ".".join(name.split("/"))
        
        if self.adfsdisc.disc_type.find("adE") == 0:
        
            if type(obj[1]) != type([]) and "." not in new_name:
            
                # Construct a suffix from the object's load address/filetype.
                
                info_handler = self.info_handlers.get(obj[2] & 0xfff00, None)
                
                # Provide default values for the file type, MIME type and
                # length.
                filetype = (obj[2] >> 8) & 0xfff
                mimetype = None
                length = obj[4]
                
                if info_handler:
                
                    filetype, mimetype, length = info_handler(
                        obj, filetype, mimetype, length
                        )
                
                suffix = "%03x" % filetype
                new_name = new_name + "." + suffix
        
        return new_name
    
    def squash_info(self, obj, def_filetype, def_mimetype, def_length):
    
        # Each Squash file contains the length of the data they
        # contain once it is decompressed.
        
        try:
        
            length = self.adfsdisc.str2num(4, obj[1][4:8])
        
        except IndexError:
        
            # Use the default length supplied.
            length = def_length
        
        # For Squash files, use the filetype in the header for
        # this file's suffix. (Use the disc image's str2num
        # method to extract the value from the file.)
        
        try:
        
            filetype = (
                self.adfsdisc.str2num(4, obj[1][8:12]) >> 8
                ) & 0xfff
        
        except IndexError:
        
            filetype = 0xfca
        
        # Let the client discover the MIME type by reading
        # the file.
        mimetype = None
        
        return filetype, mimetype, length
    
    def nspark_info(self, obj, def_filetype, def_mimetype, def_length):
    
        # For the archive as a whole, we run the nspark utility with
        # a contradictory set of options.
        
        #command = "nspark -qtv"
        
        # For now, just return the default values.
        return def_filetype, def_mimetype, def_length


if __name__ == "__main__":

    if len(sys.argv) < 3:
    
        sys.stderr.write(
            "Usage: %s [fuse options] <mount point> <image>\n" % sys.argv[0]
            )
        sys.exit(1)

    mount_point = os.path.abspath(sys.argv[-2])
    
    if not os.path.exists(mount_point):
    
        os.mkdir(mount_point)
    
    elif not os.path.isdir(mount_point):
    
        sys.stderr.write("Cannot use %s as a mount point\n" % mount_point)
        sys.exit(1)
    
    server = ADFS(sys.argv[:-1], path = sys.argv[-1])
    server.multithreaded = 1
    server.main()
    
    sys.exit(0)
