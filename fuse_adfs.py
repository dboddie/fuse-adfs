#! /usr/bin/env python

"""
fuse_adfs.py

A FUSE filesystem for ADFS disc images.

Copyright (C) 2008 David Boddie <david@boddie.org.uk>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import errno, os, struct, sys, time
from os.path import stat

import fuse
from fuse import Fuse
fuse.fuse_python_api = (0, 2)

import ADFSlib

__author__ = "David Boddie <david@boddie.org.uk>"
__version__ = "0.20"
__date__ = "Sunday 29th June 2008"
__license__ = "GNU General Public License (version 3)"


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

class ADFSstat(fuse.Stat):

    def __init__(self):
    
        fuse.Stat.__init__(self)
        
        self.st_atime = 0
        self.st_ctime = 0
        self.st_dev = 0
        self.st_gid = os.getgid()
        self.st_ino = 0
        self.st_mode = 0
        self.st_mtime = 0
        self.st_nlink = 0
        self.st_size = 0
        self.st_uid = os.getuid()


class File:

    def __init__(self, name, data, load, exec_, length):
    
        self.name = name
        self.data = data
        self.load = load
        self.exec_ = exec_
        self.length = length
    
    def stat(self):
    
        info = ADFSstat()
        info.st_mode = stat.S_IFREG | stat.S_IRUSR
        info.st_size = len(self.data)
        info.st_mtime = from_riscos_time(self.load, self.exec_)
        info.st_nlink = 1
        return info

class Directory:

    def __init__(self, name, objects, time_stamp):
    
        self.name = name
        self.objects = objects
        self.time_stamp = time_stamp
    
    def __repr__(self):
    
        return '<Directory "%s">' % self.name
    
    def stat(self):
    
        info = ADFSstat()
        info.st_mode = stat.S_IFDIR | stat.S_IRUSR | stat.S_IXUSR
        info.st_mtime = self.time_stamp
        info.st_nlink = 2
        return info
    
    def contents(self):
    
        objs = []
        for obj in self.objects:
        
            if isinstance(obj, ADFSlib.ADFSfile):
                objs.append(File(obj.name, obj.data, obj.load_address, obj.execution_address, obj.length))
            else:
                objs.append(Directory(obj.name, obj.files, self.time_stamp))
        
        return objs


class ADFS(Fuse):

    def __init__(self, *args, **kwargs):
    
        Fuse.__init__(self, *args, **kwargs)
        
        self.info_handlers = \
        {
            0xfca00:    self.squash_info,
            0xddc00:    self.nspark_info
        }
    
    def main(self):
    
        if hasattr(self, "image"):
            path = self.image
        else:
            raise ADFS_Error, "No path specified"
        
        try:
        
            self.adffile = open(path, "rb")
            self.adfsdisc = ADFSlib.ADFSdisc(self.adffile, verify = 1)
        
        except IOError:
        
            raise ADFS_Error, "Failed to open the image file specified"
        
        except ADFSlib.ADFS_exception:
        
            self.adffile.close()
            raise ADFS_Error
        
        self.root_time = time.time()
        
        return Fuse.main(self)
    
    def getattr(self, path):
    
        obj = self.find_file_within_image(path)
        
        if obj is None:
        
            return -1
        
        return obj.stat()
    
    def readlink(self, path):
    
        # readlink is not supported
        return -1
    
    def readdir(self, path, offset):
    
        obj = self.find_file_within_image(path)
        
        if obj is not None and isinstance(obj, Directory):
        
            for entry in obj.contents():
            
                yield fuse.Direntry(self.encode_name_from_object(entry))
    
    def unlink(self, path):
    
        # unlink is not supported
        return -1
    
    def rmdir(self, path):
    
        # rmdir is not supported
        return -1
    
    def symlink(self, src, dest):
    
        # symlink is not supported
        return -1
    
    def rename(self, src, dest):
    
        # rename is not supported
        return -1
    
    def link(self, src, dest):
    
        # link is not supported
        return -errno.ENOLINK
    
    def chmod(self, path, mode):
    
        # chmod is not supported
        return -1
    
    def chown(self, path, user, group):
    
        # chown is not supported
        return -1
    
    def truncate(self, path, size):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            return -1
        
        return obj.data[:size]
    
    def mknod(self, path, mode, dev):
    
        # mknod is not supported
        return -1
    
    def mkdir(self, path, mode):
    
        # mkdir is not supported
        return -1
    
    def utime(self, path, times):
    
        # utime is not supported
        return -1
    
    def open(self, path, flags):
    
        if flags & (os.O_WRONLY | os.O_RDWR) != 0:
        
            # This filesystem is read-only.
            return -errno.EACCES
        
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            return -errno.ENOENT
        
        return 0
    
    def read(self, path, length, offset):
    
        obj = self.find_file_within_image(path)
        
        if obj is None or isinstance(obj, Directory):
        
            return -errno.ENOENT
        
        return obj.data[offset:offset+length]
    
    def write(self, path, buf, offset):
    
        # write is not supported
        return -errno.EACCES
    
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
            return Directory("/", objs, self.root_time)
        
        for this_obj in objs:
        
            # Examine each object and compare its name to the next path
            # element.
            
            if isinstance(this_obj, ADFSlib.ADFSfile):
            
                # A file is found. 
                obj_name = self.encode_name_from_entry(this_obj)
                
                if obj_name == elements[0]:
                
                    # A match between names.
                    
                    if len(elements) == 1:
                    
                        # This is the last path element; we have found the
                        # required file.
                        return File(
                            this_obj.name, this_obj.data, this_obj.load_address,
                            this_obj.execution_address, this_obj.length
                            )
                    
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
                            (this_obj.name, this_obj.load_address,
                             this_obj.execution_address, this_obj.length)
                        
                        return File(this_obj[0] + ".inf", file_data,
                                    0, 0, len(file_data))
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
                        return Directory(this_obj.name, this_obj.files,
                                         self.root_time)
                    
                    else:
                    
                        # More path elements need to be satisfied; descend
                        # further.
                        return self.find_file_within_image(
                            "/".join(elements[1:]), this_obj.files
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
                ADFSlib.ADFSfile(obj.name, obj.data, obj.load, obj.exec_, obj.length)
                )
        
        else:
        
            return ".".join(obj.name.split("/"))
    
    def encode_name_from_entry(self, obj):
    
        name = obj.name
        
        # If the name contains a slash then replace it with a dot.
        new_name = ".".join(name.split("/"))
        
        if self.adfsdisc.disc_type.find("adE") == 0:
        
            if isinstance(obj, ADFSlib.ADFSfile) and "." not in new_name:
            
                # Construct a suffix from the object's load address/filetype.
                
                info_handler = self.info_handlers.get(obj.load_address & 0xfff00, None)
                
                # Provide default values for the file type, MIME type and
                # length.
                filetype = obj.filetype()
                mimetype = None
                length = obj.length
                
                if info_handler:
                
                    filetype, mimetype, length = info_handler(
                        obj, filetype, mimetype, length
                        )
                
                new_name = new_name + "." + filetype
        
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

    usage = ("fuse_adfs version %(version)s (%(date)s)\n"
             "Licensed under the %(license)s.\n\n"
             "Usage: %(app)s <mount point> [fuse options]\n\n"
             "Mounts a disk image at the specified mount point.\n"
             'Use fusermount -u <mount point> to dismount the image later.\n\n'
             "Example: %(app)s /tmp/image -o image=FloppyDisc.adf\n"
             ) % {"app": sys.argv[0], "version": __version__,
                  "date": __date__, "license": __license__}
    
    server = ADFS(version="%prog " + fuse.__version__, usage=usage)
    server.parser.add_option(mountopt="image", metavar="IMAGE", default="",
                             help="specify ADFS disk image")
    server.parse(values=server, errex=1)
    
    try:
        server.main()
    
    except ADFS_Error:
        sys.stderr.write(usage)
        sys.exit(1)
    
    sys.exit(0)
