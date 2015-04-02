""":mod:`wand.cli` --- Parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Experimental ImageMagick CLI parser

.. versionadded:: ???

"""
import collections
import ctypes

from .api import library, libmagick

__all__ = 'Parser'

library.MagickCommandGenesis.argtypes = [ctypes.c_void_p,                  # ImageInfo *
                                         ctypes.c_void_p,                  # (* MagickCommand)
                                         ctypes.c_int,                     # int
                                         ctypes.POINTER(ctypes.c_char_p),  # char **
                                         ctypes.POINTER(ctypes.c_char_p),  # char **
                                         ctypes.c_void_p]                  # ExceptionInfo *
library.MagickCommandGenesis.restype = ctypes.c_int
libmagick.AcquireImageInfo.argtypes = []
libmagick.AcquireImageInfo.restype = ctypes.c_void_p
libmagick.DestroyImageInfo.argtypes = [ctypes.c_void_p]
libmagick.DestroyImageInfo.restype = ctypes.c_void_p
libmagick.CatchException.argtypes = [ctypes.c_void_p]


class Parser(object):
    """Parser object. Digest complete CLI commands, and binds
    formatted arguments when calling. Example usage::

        from wand.cli import Parser
        # Bind CLI command
        with Parser('convert {source} -resize 64x64 {output}' as cli:
            cli(source='dragon.gif', output='resize_dragon.gif')
        # Call direct ImageMagick command
        Parser().run([' montage', 'balloon.gif', 'medical.gif', 'present.gif', 'shading.gif', 'montage.jpg'])

    :Notice:
    : - This class is experimental. Methods, behaviour, and structure are due to change.
    : - ImageMagick utility commands will write to stdout & stderr. Mixing with other
        Python streams, pip, & IO libraries will result in undefined behaviour.

    :param command: CLI string to execute.
    :type command: :class:`basestring`
    """
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
        """
        Defines CLI instructions to bind when class is called.

        :param command: CLI command to execute
        :type command: :class:`basestring`
        :returns Parser: instance of Parser for method changing.
        :rtype Parser:
        """
        if not isinstance(command, basestring):
            raise TypeError('Expecting basestring, not %s' % repr(command))
        self.command = command.strip()
        return self

    def find_utility(self, utility):
        """
        Maps command utility term to library function-pointer

        :param utility: Utility name to map API function pointer
        :type utility: :class:`basestring`
        :returns: ImageMagick function reference.
        """
        if utility not in self.utilities:
            raise ValueError('Expecting ImageMagick utility, not %s' % repr(utility))
        return self.utilities[utility]

    def run(self, arguments):
        """
        Allocates & executes ImageMagick command with given arguments.
        :param arguments: List of words to be converted to C's 'char ** argv'
        :type arguments: :class:`collections.Sequence`
        :return: `bool` True on success
        """
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
        # Metadata reference to char pointer. Default this to NULL (void *)
        meta = None
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
