""":mod:`wand.cli` --- Parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Experimental ImageMagick CLI parser

.. versionadded:: ???

"""
import collections
import ctypes

from .api import library, libmagick

__all__ = 'Parser'

library.MagickCommandGenesis.argtypes = [ctypes.c_void_p,
                                         ctypes.c_void_p,
                                         ctypes.c_int,
                                         ctypes.POINTER(ctypes.c_char_p),
                                         ctypes.POINTER(ctypes.c_char_p),
                                         ctypes.c_void_p]
library.MagickCommandGenesis.restype = ctypes.c_int
libmagick.AcquireImageInfo.argtypes = []
libmagick.AcquireImageInfo.restype = ctypes.c_void_p
libmagick.DestroyImageInfo.argtypes = [ctypes.c_void_p]
libmagick.DestroyImageInfo.restype = ctypes.c_void_p
libmagick.CatchException.argtypes = [ctypes.c_void_p]


class Parser(object):
    utilities = {'animate': library.AnimateImageCommand,
                 'compare': library.CompareImageCommand,
                 'composite': library.CompositeImageCommand,
                 'conjure': library.ConjureImageCommand,
                 'convert': library.ConvertImageCommand,
                 'display': library.DisplayImageCommand,
                 'identify': library.IdentifyImageCommand,
                 'import': library.ImportImageCommand,
                 'mogrify': library.MogrifyImageCommand,
                 'stream': library.StreamImageCommand}

    def __init__(self, command=None):
        self.command = ''
        if command:
            self.set_command(command)

    def __call__(self, **kwargs):
        command = self.command.format(**kwargs)
        return self.run(command.split())

    def set_command(self, command):
        if not isinstance(command, basestring):
            raise TypeError('Expecting basestring, not %s' % repr(command))
        self.command = command.strip()
        return self

    def find_utility(self, utility):
        """
        Maps command utility term to library function-pointer
        """
        if utility not in self.utilities:
            raise ValueError('Expecting ImageMagick utility, not %s' % repr(utility))
        return self.utilities[utility]

    def run(self, arguments):
        if not isinstance(arguments, collections.Sequence):
            raise TypeError('Expecting sequence of ImageMagick instructions, not %s' % repr(arguments))
        # Allocate ImageInfo
        image_info = libmagick.AcquireImageInfo()
        # Find command-utility pointer
        func = self.find_utility(arguments[0])
        # Argument count
        argument_count = len(arguments)
        # Convert arguments to C types
        c_arguments = (ctypes.c_char_p * argument_count)(*arguments)
        # Meta pointer-pointer (? no idea ?)
        meta = (ctypes.c_char_p * 1)()
        # Allocate Exception handler
        exception = libmagick.AcquireExceptionInfo()
        # Genesis Magick Suite
        ok = library.MagickCommandGenesis(image_info, func, argument_count, c_arguments, meta, exception)
        # Dump any errors/warning/messages to user
        libmagick.CatchException(exception)
        # Free allocated resource
        libmagick.DestroyImageInfo(image_info)
        libmagick.DestroyExceptionInfo(exception)
        return ok
