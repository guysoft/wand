""":mod:`wand.api` --- Low-level interfaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionchanged:: 0.1.10
   Changed to throw :exc:`~exceptions.ImportError` instead of
   :exc:`~exceptions.AttributeError` when the shared library fails to load.

"""
import ctypes
import ctypes.util
import itertools
import os
import os.path
import platform
import sys
import traceback

__all__ = ('MagickPixelPacket', 'PointInfo', 'AffineMatrix', 'c_magick_char_p',
           'library', 'libc', 'libmagick', 'load_library')


class c_magick_char_p(ctypes.c_char_p):
    """This subclass prevents the automatic conversion behavior of
    :class:`ctypes.c_char_p`, allowing memory to be properly freed in the
    destructor.  It must only be used for non-const character pointers
    returned by ImageMagick functions.

    """

    def __del__(self):
        """Relinquishes memory allocated by ImageMagick.
        We don't need to worry about checking for ``NULL`` because
        :c:func:`MagickRelinquishMemory` does that for us.
        Note alslo that :class:`ctypes.c_char_p` has no
        :meth:`~object.__del__` method, so we don't need to
        (and indeed can't) call the superclass destructor.

        """
        library.MagickRelinquishMemory(self)


def find_library(suffix=''):
    """Finds library path to try loading.  The result paths are not
    guaranteed that they exist.

    :param suffix: optional suffix e.g. ``'-Q16'``
    :type suffix: :class:`basestring`
    :returns: a pair of libwand and libmagick paths.  they can be the same.
              path can be ``None`` as well
    :rtype: :class:`tuple`

    """
    libwand = None
    system = platform.system()
    magick_home = os.environ.get('MAGICK_HOME')
    if magick_home:
        if system == 'Windows':
            libwand = 'CORE_RL_wand_{0}.dll'.format(suffix),
        elif system == 'Darwin':
            libwand = 'lib', 'libMagickWand{0}.dylib'.format(suffix),
        else:
            libwand = 'lib', 'libMagickWand{0}.so'.format(suffix),
        libwand = os.path.join(magick_home, *libwand)
    else:
        if system == 'Windows':
            libwand = ctypes.util.find_library('CORE_RL_wand_' + suffix)
        else:
            libwand = ctypes.util.find_library('MagickWand' + suffix)
    if system == 'Windows':
        # On Windows, the API is split between two libs. On other platforms,
        # it's all contained in one.
        libmagick_filename = 'CORE_RL_magick_' + suffix
        if magick_home:
            libmagick = os.path.join(magick_home, libmagick_filename + '.dll')
        else:
            libmagick = ctypes.util.find_library(libmagick_filename)
        return libwand, libmagick
    return libwand, libwand


def load_library():
    """Loads the MagickWand library.

    :returns: the MagickWand library and the ImageMagick library
    :rtype: :class:`ctypes.CDLL`

    """
    tried_paths = []
    versions = ('', '-Q16', '-Q8', '-6.Q16')
    options = ('', 'HDRI')
    combinations = itertools.product(versions, options)
    for suffix in (version + option for version, option in combinations):
        libwand_path, libmagick_path = find_library(suffix)
        if libwand_path is None or libmagick_path is None:
            continue
        tried_paths.append(libwand_path)
        try:
            libwand = ctypes.CDLL(libwand_path)
            if libwand_path == libmagick_path:
                libmagick = libwand
            else:
                tried_paths.append(libmagick_path)
                libmagick = ctypes.CDLL(libmagick_path)
        except (IOError, OSError):
            continue
        return libwand, libmagick
    raise IOError('cannot find library; tried paths: ' + repr(tried_paths))


if not hasattr(ctypes, 'c_ssize_t'):
    if ctypes.sizeof(ctypes.c_uint) == ctypes.sizeof(ctypes.c_void_p):
        ctypes.c_ssize_t = ctypes.c_int
    elif ctypes.sizeof(ctypes.c_ulong) == ctypes.sizeof(ctypes.c_void_p):
        ctypes.c_ssize_t = ctypes.c_long
    elif ctypes.sizeof(ctypes.c_ulonglong) == ctypes.sizeof(ctypes.c_void_p):
        ctypes.c_ssize_t = ctypes.c_longlong


class MagickPixelPacket(ctypes.Structure):

    _fields_ = [('storage_class', ctypes.c_int),
                ('colorspace', ctypes.c_int),
                ('matte', ctypes.c_int),
                ('fuzz', ctypes.c_double),
                ('depth', ctypes.c_size_t),
                ('red', ctypes.c_double),
                ('green', ctypes.c_double),
                ('blue', ctypes.c_double),
                ('opacity', ctypes.c_double),
                ('index', ctypes.c_double)]

class PointInfo(ctypes.Structure):

    _fields_ = [('x', ctypes.c_double),
                ('y', ctypes.c_double)]

class AffineMatrix(ctypes.Structure):
    _fields_ = [('sx', ctypes.c_double),
                ('rx', ctypes.c_double),
                ('ry', ctypes.c_double),
                ('sy', ctypes.c_double),
                ('tx', ctypes.c_double),
                ('ty', ctypes.c_double)]


# Preserve the module itself even if it fails to import
sys.modules['wand._api'] = sys.modules['wand.api']

try:
    libraries = load_library()
except (OSError, IOError):
    msg = 'http://docs.wand-py.org/en/latest/guide/install.html'
    if sys.platform.startswith('freebsd'):
        msg = 'pkg_add -r'
    elif sys.platform == 'win32':
        msg += '#install-imagemagick-on-windows'
    elif sys.platform == 'darwin':
        mac_pkgmgrs = {'brew': 'brew install freetype imagemagick',
                       'port': 'port install imagemagick'}
        for pkgmgr in mac_pkgmgrs:
            with os.popen('which ' + pkgmgr) as f:
                if f.read().strip():
                    msg = mac_pkgmgrs[pkgmgr]
                    break
        else:
            msg += '#install-imagemagick-on-mac'
    else:
        distname, _, __ = platform.linux_distribution()
        distname = (distname or '').lower()
        if distname in ('debian', 'ubuntu'):
            msg = 'apt-get install libmagickwand-dev'
        elif distname in ('fedora', 'centos', 'redhat'):
            msg = 'yum install ImageMagick-devel'
    raise ImportError('MagickWand shared library not found.\n'
                      'You probably had not installed ImageMagick library.\n'
                      'Try to install:\n  ' + msg)

#: (:class:`ctypes.CDLL`) The MagickWand library.
library = libraries[0]

#: (:class:`ctypes.CDLL`) The ImageMagick library.  It is the same with
#: :data:`library` on platforms other than Windows.
#:
#: .. versionadded:: 0.1.10
libmagick = libraries[1]

try:
    #######################
    # Magick Core methods #
    #######################
    libmagick.AcquireExceptionInfo.argtypes = []
    libmagick.AcquireExceptionInfo.restype = ctypes.c_void_p
    libmagick.CloneImages.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                      ctypes.c_void_p]
    libmagick.CloneImages.restype = ctypes.c_void_p
    libmagick.DestroyExceptionInfo.argtypes = [ctypes.c_void_p]
    libmagick.DestroyExceptionInfo.restype = ctypes.c_void_p

    # These functions are const so it's okay for them to be c_char_p
    libmagick.GetMagickVersion.argtypes = [ctypes.POINTER(ctypes.c_size_t)]
    libmagick.GetMagickVersion.restype = ctypes.c_char_p

    libmagick.GetMagickReleaseDate.argtypes = []
    libmagick.GetMagickReleaseDate.restype = ctypes.c_char_p

    libmagick.GetMagickQuantumDepth.argtypes = [
        ctypes.POINTER(ctypes.c_size_t)
    ]
    libmagick.GetMagickQuantumDepth.restype = ctypes.c_char_p
    libmagick.GetNextImageInList.argtypes = [ctypes.c_void_p]
    libmagick.GetNextImageInList.restype = ctypes.c_void_p
    libmagick.MagickToMime.argtypes = [ctypes.c_char_p]
    libmagick.MagickToMime.restype = c_magick_char_p

    #######################
    # Magick Wand methods #
    #######################
    #
    # Magick Wand Methods
    # http://www.imagemagick.org/script/magick-wand.php
    library.ClearMagickWand.argtypes = [ctypes.c_void_p]
    library.CloneMagickWand.argtypes = [ctypes.c_void_p]
    library.CloneMagickWand.restype = ctypes.c_void_p
    library.DestroyMagickWand.argtypes = [ctypes.c_void_p]
    library.DestroyMagickWand.restype = ctypes.c_void_p
    library.IsMagickWand.argtypes = [ctypes.c_void_p]
    library.IsMagickWandInstantiated.argtypes = []
    library.MagickClearException.argtypes = [ctypes.c_void_p]
    library.MagickGetException.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_int)]
    library.MagickGetException.restype = c_magick_char_p
    library.MagickGetExceptionType.argtypes = [ctypes.c_void_p]
    library.MagickGetExceptionType.restype = ctypes.c_int
    library.MagickGetIteratorIndex.argtypes = [ctypes.c_void_p]
    library.MagickGetIteratorIndex.restype = ctypes.c_ssize_t
    library.MagickQueryConfigureOption.argtypes = [ctypes.c_char_p]
    library.MagickQueryConfigureOption.restype = c_magick_char_p
    library.MagickQueryConfigureOptions.argtypes = [ctypes.c_char_p,
                                                    ctypes.POINTER(ctypes.c_size_t)]
    library.MagickQueryConfigureOptions.restype = ctypes.POINTER(c_magick_char_p)
    library.MagickQueryFontMetrics.argtypes = [ctypes.c_void_p,
                                               ctypes.c_void_p,
                                               ctypes.c_char_p]
    library.MagickQueryFontMetrics.restype = ctypes.POINTER(ctypes.c_double)
    library.MagickQueryMultilineFontMetrics.argtypes = [ctypes.c_void_p,
                                                        ctypes.c_void_p,
                                                        ctypes.c_char_p]
    library.MagickQueryMultilineFontMetrics.restype = ctypes.POINTER(ctypes.c_double)
    library.MagickQueryFonts.argtypes = [ctypes.c_char_p,
                                         ctypes.POINTER(ctypes.c_size_t)]
    library.MagickQueryFonts.restype = ctypes.POINTER(c_magick_char_p)
    library.MagickQueryFormats.argtypes = [ctypes.c_char_p,
                                           ctypes.POINTER(ctypes.c_size_t)]
    library.MagickQueryFormats.restype = ctypes.POINTER(c_magick_char_p)
    library.MagickRelinquishMemory.argtypes = [ctypes.c_void_p]
    library.MagickRelinquishMemory.restype = ctypes.c_void_p
    library.MagickResetIterator.argtypes = [ctypes.c_void_p]
    library.MagickSetFirstIterator.argtypes = [ctypes.c_void_p]
    library.MagickSetIteratorIndex.argtypes = [ctypes.c_void_p,
                                               ctypes.c_ssize_t]
    library.MagickSetLastIterator.argtypes = [ctypes.c_void_p]
    library.MagickWandGenesis.argtypes = []
    library.MagickWandTerminus.argtypes = []
    library.NewMagickWand.argtypes = []
    library.NewMagickWand.restype = ctypes.c_void_p
    library.NewMagickWandFromImage.argtypes = [ctypes.c_void_p]
    library.NewMagickWandFromImage.restype = ctypes.c_void_p

    #
    # Set or Get Magick Wand Properties
    # http://www.imagemagick.org/api/magick-property.php
    library.MagickDeleteImageArtifact.argtypes = [ctypes.c_void_p,
                                                  ctypes.c_char_p]
    library.MagickDeleteImageProperty.argtypes = [ctypes.c_void_p,
                                                  ctypes.c_char_p]
    library.MagickDeleteOption.argtypes = [ctypes.c_void_p,
                                           ctypes.c_char_p]
    library.MagickGetAntialias.argtypes = [ctypes.c_void_p]
    library.MagickGetAntialias.restype = ctypes.c_int
    library.MagickGetBackgroundColor.argtypes = [ctypes.c_void_p]
    library.MagickGetBackgroundColor.restype = ctypes.c_void_p
    library.MagickGetColorspace.argtypes = [ctypes.c_void_p]
    library.MagickGetColorspace.restype = ctypes.c_int
    library.MagickGetCompression.argtypes = [ctypes.c_void_p]
    library.MagickGetCompression.restype = ctypes.c_int
    library.MagickGetCompressionQuality.argtypes = [ctypes.c_void_p]
    library.MagickGetCompressionQuality.restype = ctypes.c_size_t
    # library.MagickGetCopyright
    # library.MagickGetFilename
    library.MagickGetCopyright.restype = c_magick_char_p
    library.MagickGetFont.argtypes = [ctypes.c_void_p]
    library.MagickGetFont.restype = ctypes.c_char_p
    # library.MagickGetFormat
    library.MagickGetGravity.argtypes = [ctypes.c_void_p]
    library.MagickGetGravity.restype = ctypes.c_int
    # library.MagickGetHomeURL
    # library.MagickGetImageArtifact
    # library.MagickGetImageArtifacts
    # library.MagickGetImageProfile
    # library.MagickGetImageProfiles
    library.MagickGetImageProperty.argtypes = [ctypes.c_void_p,
                                               ctypes.c_char_p]
    library.MagickGetImageProperty.restype = c_magick_char_p

    library.MagickGetImageProperties.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_char_p,
                                                 ctypes.POINTER(ctypes.c_size_t)]
    library.MagickGetImageProperties.restype = ctypes.POINTER(ctypes.c_char_p)
    # library.MagickGetInterlaceScheme
    # library.MagickGetInterpolateMethod
    library.MagickGetOption.argtypes = [ctypes.c_void_p,
                                        ctypes.c_char_p]
    library.MagickGetOption.restype = ctypes.c_char_p
    # library.MagickGetOptions
    # library.MagickGetOrientation
    # library.MagickGetPackageName
    # library.MagickGetPage
    library.MagickGetPointsize.argtypes = [ctypes.c_void_p]
    library.MagickGetPointsize.restype = ctypes.c_double
    # library.MagickGetQuantumDepth
    library.MagickGetQuantumRange.argtypes = [ctypes.POINTER(ctypes.c_size_t)]
    # library.MagickGetReleaseDate
    # library.MagickGetResolution
    # library.MagickGetResource
    # library.MagickGetResourceLimit
    # library.MagickGetSamplingFactors
    library.MagickGetSize.argtypes = [ctypes.c_void_p,
                                      ctypes.POINTER(ctypes.c_uint),
                                      ctypes.POINTER(ctypes.c_uint)]
    library.MagickGetSize.restype = ctypes.c_int
    # library.MagickGetSizeOffset
    # library.MagickGetType
    # library.MagickGetVersion
    # library.MagickProfileImage
    # library.MagickRemoveImageProfile
    library.MagickSetAntialias.argtypes = [ctypes.c_void_p,
                                           ctypes.c_int]
    library.MagickSetAntialias.restype = ctypes.c_int
    library.MagickSetBackgroundColor.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_void_p]
    library.MagickSetBackgroundColor.restype = ctypes.c_int
    # library.MagickSetColorspace
    # library.MagickSetCompression
    # library.MagickSetCompressionQuality
    # library.MagickSetDepth
    # library.MagickSetExtract
    library.MagickSetFilename.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    library.MagickSetFont.argtypes = [ctypes.c_void_p,
                                      ctypes.c_char_p]
    library.MagickSetFont.restype = ctypes.c_int
    # library.MagickSetFormat
    library.MagickSetGravity.argtypes = [ctypes.c_void_p,
                                         ctypes.c_int]
    library.MagickSetGravity.restype = ctypes.c_int
    # library.MagickSetImageArtifact
    # library.MagickSetImageProfile
    library.MagickSetImageProperty.argtypes = [ctypes.c_void_p,
                                               ctypes.c_char_p,
                                               ctypes.c_char_p]
    # library.MagickSetInterlaceScheme
    # library.MagickSetInterpolateMethod
    library.MagickSetOption.argtypes = [ctypes.c_void_p,
                                        ctypes.c_char_p,
                                        ctypes.c_char_p]
    library.MagickSetOption.restype = ctypes.c_int
    # library.MagickSetOrientation
    # library.MagickSetPage
    # library.MagickSetPassphrase
    library.MagickSetPointsize.argtypes = [ctypes.c_void_p,
                                           ctypes.c_double]
    library.MagickSetPointsize.restype = ctypes.c_int
    # library.MagickSetProgressMonitor
    # library.MagickSetResourceLimit
    library.MagickSetResolution.argtypes = [ctypes.c_void_p, ctypes.c_double,
                                            ctypes.c_double]
    # library.MagickSetSamplingFactors
    library.MagickSetSize.argtypes = [ctypes.c_void_p,
                                      ctypes.c_uint,
                                      ctypes.c_uint]
    library.MagickSetSize.restype = ctypes.c_int
    # library.MagickSetSizeOffset
    # library.MagickSetType

    #
    # Magick Wand Image Methods
    # http://www.imagemagick.org/api/magick-image.php
    library.GetImageFromMagickWand.argtypes = [ctypes.c_void_p]
    library.GetImageFromMagickWand.restype = ctypes.c_void_p
    # library.MagickAdaptiveBlurImage
    # library.MagickAdaptiveResizeImage
    # library.MagickAdaptiveSharpenImage
    # library.MagickAdaptiveThresholdImage
    library.MagickAddImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    # library.MagickAddNoiseImage
    # library.MagickAffineTransformImage
    library.MagickAnnotateImage.argtypes = [ctypes.c_void_p,
                                            ctypes.c_void_p,
                                            ctypes.c_double,
                                            ctypes.c_double,
                                            ctypes.c_double,
                                            ctypes.c_char_p]
    library.MagickAnnotateImage.restype = ctypes.c_int
    # library.MagickAnimateImages
    library.MagickAppendImages.argtypes = [ctypes.c_void_p,
                                           ctypes.c_int]
    library.MagickAppendImages.restype = ctypes.c_void_p
    # library.MagickAutoGammaImage
    # library.MagickAutoLevelImage
    try:
        library.MagickAutoOrientImage.argtypes = [ctypes.c_void_p]
    except AttributeError:
        # MagickAutoOrientImage was added in 6.8.9+, we have a fallback function
        # so we pass silently if we cant import it
        pass
    # library.MagickBlackThresholdImage
    # library.MagickBlueShiftImage
    # library.MagickBlurImage
    library.MagickBorderImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_size_t, ctypes.c_size_t]
    # library.MagickBrightnessContrastImage
    # library.MagickChannelFxImage
    # library.MagickCharcoalImage
    # library.MagickChopImage
    # library.MagickClampImage
    # library.MagickClipImage
    # library.MagickClipImagePath
    # library.MagickClutImage
    library.MagickCoalesceImages.argtypes = [ctypes.c_void_p]
    library.MagickCoalesceImages.restype = ctypes.c_void_p
    # library.MagickColorDecisionListImage
    # library.MagickColorizeImage
    # library.MagickColorMatrixImage
    # library.MagickCombineImages
    # library.MagickCommentImage
    # library.MagickCompareImages
    # library.MagickCompareImagesLayers
    library.MagickCompositeImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                             ctypes.c_int, ctypes.c_ssize_t,
                                             ctypes.c_ssize_t]
    library.MagickCompositeImageChannel.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_ssize_t, ctypes.c_ssize_t
    ]
    # library.MagickCompositeLayers
    # library.MagickContrastImage
    library.MagickContrastStretchImage.argtypes = [ctypes.c_void_p,  # wand
                                                   ctypes.c_double,  # black
                                                   ctypes.c_double]  # white

    library.MagickContrastStretchImageChannel.argtypes = [ctypes.c_void_p,  # wand
                                                          ctypes.c_int,     # channel
                                                          ctypes.c_double,  # black
                                                          ctypes.c_double]  # white
    # library.MagickConvolveImage
    library.MagickCropImage.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_size_t, ctypes.c_ssize_t,
                                        ctypes.c_ssize_t]
    # library.MagickCycleColormapImage
    # library.MagickConstituteImage
    # library.MagickDecipherImage
    # library.MagickDeconstructImages
    # library.MagickDeskewImage
    # library.MagickDespeckleImage
    # library.MagickDestroyImage
    # library.MagickDisplayImage
    # library.MagickDisplayImages
    library.MagickDistortImage.argtypes = [ctypes.c_void_p,  # wand
                                           ctypes.c_int,     # method
                                           ctypes.c_size_t,  # number_arguments
                                           ctypes.POINTER(ctypes.c_double),  # arguments
                                           ctypes.c_int]     # bestfit
    library.MagickDistortImage.restype = ctypes.c_int
    library.MagickDrawImage.argtypes = [ctypes.c_void_p,
                                        ctypes.c_void_p]
    library.MagickDrawImage.restype = ctypes.c_int
    # library.MagickEdgeImage
    # library.MagickEmbossImage
    # library.MagickEncipherImage
    # library.MagickEnhanceImage
    library.MagickEqualizeImage.argtypes = [ctypes.c_void_p]
    library.MagickEvaluateImage.argtypes = [ctypes.c_void_p,
                                            ctypes.c_int,
                                            ctypes.c_double]

    library.MagickEvaluateImageChannel.argtypes = [ctypes.c_void_p,
                                                   ctypes.c_int,
                                                   ctypes.c_int,
                                                   ctypes.c_double]
    # library.MagickExportImagePixels
    # library.MagickExtentImage
    library.MagickFlipImage.argtypes = [ctypes.c_void_p]
    # library.MagickFloodfillPaintImage
    library.MagickFlopImage.argtypes = [ctypes.c_void_p]
    # library.MagickForwardFourierTransformImage
    library.MagickFrameImage.argtypes = [ctypes.c_void_p,   # wand
                                         ctypes.c_void_p,   # matte_color
                                         ctypes.c_size_t,   # width
                                         ctypes.c_size_t,   # height
                                         ctypes.c_ssize_t,  # inner_bevel
                                         ctypes.c_ssize_t]  # outer_bevel
    library.MagickFunctionImage.argtypes = [ctypes.c_void_p,  # wand
                                            ctypes.c_int,     # MagickFunction
                                            ctypes.c_size_t,  # number_arguments
                                            ctypes.POINTER(ctypes.c_double)]  # arguments

    library.MagickFunctionImageChannel.argtypes = [ctypes.c_void_p,  # wand
                                                   ctypes.c_int,     # channel
                                                   ctypes.c_int,     # MagickFunction
                                                   ctypes.c_size_t,  # number_arguments
                                                   ctypes.POINTER(ctypes.c_double)]  # arguments
    library.MagickFxImage.argtypes = [ctypes.c_void_p,  # wand
                                      ctypes.c_char_p]  # expression
    library.MagickFxImage.restype = ctypes.c_void_p

    library.MagickFxImageChannel.argtypes = [ctypes.c_void_p,  # wand
                                             ctypes.c_int,     # channel
                                             ctypes.c_char_p]  # expression
    library.MagickFxImageChannel.restype = ctypes.c_void_p
    library.MagickGammaImage.argtypes = [ctypes.c_void_p,
                                         ctypes.c_double]

    library.MagickGammaImageChannel.argtypes = [ctypes.c_void_p,
                                                ctypes.c_int,
                                                ctypes.c_double]

    library.MagickGaussianBlurImage.argtypes = [ctypes.c_void_p,
                                                ctypes.c_double,
                                                ctypes.c_double]
    # library.MagickGetImage
    library.MagickGetImageAlphaChannel.argtypes = [ctypes.c_void_p]
    library.MagickGetImageAlphaChannel.restype = ctypes.c_size_t
    # library.MagickGetImageMask
    library.MagickGetImageBackgroundColor.argtypes = [ctypes.c_void_p,
                                                      ctypes.c_void_p]
    library.MagickGetImageBlob.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_size_t)]
    library.MagickGetImageBlob.restype = ctypes.POINTER(ctypes.c_ubyte)
    library.MagickGetImagesBlob.argtypes = [ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_size_t)]
    library.MagickGetImagesBlob.restype = ctypes.POINTER(ctypes.c_ubyte)
    # library.MagickGetImageBluePrimary
    # library.MagickGetImageBorderColor
    # library.MagickGetImageFeatures
    # library.MagickGetImageKurtosis
    # library.MagickGetImageMean
    # library.MagickGetImageRange
    # library.MagickGetImageStatistics
    # library.MagickGetImageColormapColor
    # library.MagickGetImageColors
    library.MagickGetImageColorspace.argtypes = [ctypes.c_void_p]
    library.MagickGetImageColorspace.restype = ctypes.c_int
    # library.MagickGetImageCompose
    library.MagickGetImageCompression.argtypes = [ctypes.c_void_p]
    library.MagickGetImageCompression.restype = ctypes.c_int
    library.MagickGetImageCompressionQuality.argtypes = [ctypes.c_void_p]
    library.MagickGetImageCompressionQuality.restype = ctypes.c_ssize_t
    library.MagickGetImageDelay.argtypes = [ctypes.c_void_p]
    library.MagickGetImageDelay.restype = ctypes.c_ssize_t
    library.MagickGetImageDepth.argtypes = [ctypes.c_void_p]
    library.MagickGetImageDepth.restype = ctypes.c_size_t
    library.MagickGetImageChannelDepth.argtypes = [ctypes.c_void_p,
                                                   ctypes.c_int]
    library.MagickGetImageChannelDepth.restype = ctypes.c_size_t
    # library.MagickGetImageDispose
    # library.MagickGetImageDistortion
    # library.MagickGetImageDistortions
    # library.MagickGetImageEndian
    # library.MagickGetImageFilename
    library.MagickGetImageFormat.argtypes = [ctypes.c_void_p]
    library.MagickGetImageFormat.restype = c_magick_char_p
    # library.MagickGetImageFuzz
    # library.MagickGetImageGamma
    # library.MagickGetImageGravity
    # library.MagickGetImageGreenPrimary
    library.MagickGetImageHeight.argtypes = [ctypes.c_void_p]
    library.MagickGetImageHeight.restype = ctypes.c_size_t
    library.MagickGetImageHistogram.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t)
    ]
    library.MagickGetImageHistogram.restype = ctypes.POINTER(ctypes.c_void_p)
    # library.MagickGetImageInterlaceScheme
    # library.MagickGetImageInterpolateMethod
    # library.MagickGetImageIterations
    # library.MagickGetImageLength
    library.MagickGetImageMatteColor.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_void_p]
    library.MagickGetImageOrientation.argtypes = [ctypes.c_void_p]
    library.MagickGetImageOrientation.restype = ctypes.c_int
    # library.MagickGetImagePage
    # library.MagickGetImagePixelColor
    # library.MagickGetImageRedPrimary
    # library.MagickGetImageRegion
    # library.MagickGetImageRenderingIntent
    library.MagickGetImageResolution.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double)
    ]
    # library.MagickGetImageScene
    library.MagickGetImageSignature.argtypes = [ctypes.c_void_p]
    library.MagickGetImageSignature.restype = c_magick_char_p
    # library.MagickGetImageTicksPerSecond
    library.MagickGetImageType.argtypes = [ctypes.c_void_p]
    library.MagickGetImageUnits.argtypes = [ctypes.c_void_p]
    library.MagickGetImageVirtualPixelMethod.argtypes = [ctypes.c_void_p]
    # library.MagickGetImageWhitePoint
    library.MagickGetImageWidth.argtypes = [ctypes.c_void_p]
    library.MagickGetImageWidth.restype = ctypes.c_size_t
    library.MagickGetNumberImages.argtypes = [ctypes.c_void_p]
    library.MagickGetNumberImages.restype = ctypes.c_size_t
    # library.MagickGetImageTotalInkDensity
    # library.MagickHaldClutImage
    # library.MagickHasNextImage
    # library.MagickHasPreviousImage
    library.MagickIdentifyImage.argtypes = [ctypes.c_void_p]
    library.MagickIdentifyImage.restype = ctypes.c_char_p
    # library.MagickImplodeImage
    # library.MagickImportImagePixels
    # library.MagickInterpolativeResizeImage
    # library.MagickInverseFourierTransformImage
    # library.MagickLabelImage
    # library.MagickLevelImage
    library.MagickLinearStretchImage.argtypes = [ctypes.c_void_p,  # wand
                                                 ctypes.c_double,  # black
                                                 ctypes.c_double]  # white
    library.MagickLiquidRescaleImage.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
        ctypes.c_double, ctypes.c_double
    ]
    # library.MagickMagnifyImage
    # library.MagickMergeImageLayers
    # library.MagickMinifyImage
    library.MagickModulateImage.argtypes = [ctypes.c_void_p,
                                            ctypes.c_double,
                                            ctypes.c_double,
                                            ctypes.c_double]
    # library.MagickMontageImage
    # library.MagickMorphImages
    # library.MagickMorphologyImage
    # library.MagickMotionBlurImage
    library.MagickNegateImage.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.MagickNegateImageChannel.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_int,
                                                 ctypes.c_int]
    library.MagickNewImage.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_void_p]
    # library.MagickNextImage
    library.MagickNormalizeImage.argtypes = [ctypes.c_void_p]
    library.MagickNormalizeImageChannel.argtypes = [ctypes.c_void_p,
                                                    ctypes.c_int]
    # library.MagickOilPaintImage
    # library.MagickOpaquePaintImage
    # library.MagickOptimizeImageLayers
    # library.MagickOptimizeImageTransparency
    # library.MagickOrderedPosterizeImage
    # library.MagickPingImage
    # library.MagickPingImageBlob
    # library.MagickPingImageFile
    # library.MagickPolaroidImage
    # library.MagickPosterizeImage
    # library.MagickPreviewImages
    # library.MagickPreviousImage
    # library.MagickQuantizeImage
    # library.MagickQuantizeImages
    # library.MagickRotationalBlurImage
    # library.MagickRaiseImage
    # library.MagickRandomThresholdImage
    library.MagickReadImage.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    library.MagickReadImageBlob.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_size_t]
    library.MagickReadImageFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    # library.MagickRemapImage
    library.MagickRemoveImage.argtypes = [ctypes.c_void_p]
    # library.MagickResampleImage
    library.MagickResetImagePage.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    library.MagickResizeImage.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_size_t, ctypes.c_int,
                                          ctypes.c_double]
    # library.MagickRollImage
    library.MagickRotateImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_double]
    library.MagickSampleImage.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_size_t]
    # library.MagickScaleImage
    # library.MagickSegmentImage
    # library.MagickSelectiveBlurImage
    library.MagickSeparateImageChannel.argtypes = [ctypes.c_void_p,
                                                   ctypes.c_int]
    # library.MagickSepiaToneImage
    # library.MagickSetImage
    # library.MagickSetImageAlphaChannel
    library.MagickSetImageBackgroundColor.argtypes = [ctypes.c_void_p,
                                                      ctypes.c_void_p]
    # library.MagickSetImageBluePrimary
    # library.MagickSetImageBorderColor
    # library.MagickSetImageMask
    # library.MagickSetImageColor
    # library.MagickSetImageColormapColor
    library.MagickSetImageColorspace.argtypes = [ctypes.c_void_p, ctypes.c_int]
    # library.MagickSetImageCompose
    library.MagickSetImageCompression.argtypes = [ctypes.c_void_p,
                                                  ctypes.c_int]
    library.MagickSetImageCompressionQuality.argtypes = [ctypes.c_void_p,
                                                         ctypes.c_ssize_t]
    library.MagickSetImageDelay.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t]
    library.MagickSetImageDepth.argtypes = [ctypes.c_void_p]
    # library.MagickSetImageDispose
    # library.MagickSetImageEndian
    # library.MagickSetImageExtent
    # library.MagickSetImageFilename
    library.MagickSetImageFormat.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    # library.MagickSetImageFuzz
    # library.MagickSetImageGamma
    # library.MagickSetImageGravity
    # library.MagickSetImageGreenPrimary
    # library.MagickSetImageInterlaceScheme
    # library.MagickSetImagePixelInterpolateMethod
    # library.MagickSetImageIterations
    library.MagickSetImageMatte.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.MagickSetImageMatteColor.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_void_p]
    # library.MagickSetImageAlpha
    library.MagickSetImageAlphaChannel.argtypes = [ctypes.c_void_p,
                                                   ctypes.c_int]
    library.MagickSetImageOrientation.argtypes = [ctypes.c_void_p,
                                                  ctypes.c_int]
    # library.MagickSetImagePage
    # library.MagickSetImageProgressMonitor
    # library.MagickSetImageRedPrimary
    # library.MagickSetImageRenderingIntent
    library.MagickSetImageResolution.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_double,
                                                 ctypes.c_double]
    # library.MagickSetImageScene
    # library.MagickSetImageTicksPerSecond
    library.MagickSetImageType.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.MagickSetImageUnits.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.MagickSetImageVirtualPixelMethod.argtypes = [ctypes.c_void_p, ctypes.c_int]
    # library.MagickSetImageWhitePoint
    # library.MagickShadeImage
    # library.MagickShadowImage
    # library.MagickSharpenImage
    # library.MagickShaveImage
    # library.MagickShearImage
    # library.MagickSigmoidalContrastImage
    # library.MagickSimilarityImage
    # library.MagickSketchImage
    # library.MagickSmushImages
    # library.MagickSolarizeImage
    # library.MagickSparseColorImage
    # library.MagickSpliceImage
    # library.MagickSpreadImage
    # library.MagickStatisticImage
    # library.MagickSteganoImage
    # library.MagickStereoImage
    library.MagickStripImage.argtypes = [ctypes.c_void_p]
    # library.MagickSwirlImage
    # library.MagickTextureImage
    library.MagickThresholdImage.argtypes = [ctypes.c_void_p, ctypes.c_double]

    library.MagickThresholdImageChannel.argtypes = [ctypes.c_void_p,
                                                    ctypes.c_int,
                                                    ctypes.c_double]
    # library.MagickThumbnailImage
    # library.MagickTintImage
    library.MagickTransformImage.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                             ctypes.c_char_p]
    library.MagickTransformImage.restype = ctypes.c_void_p
    # library.MagickTransformImageColorspace
    library.MagickTransparentPaintImage.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double, ctypes.c_double,
        ctypes.c_int
    ]
    library.MagickTransposeImage.argtypes = [ctypes.c_void_p]
    library.MagickTransverseImage.argtypes = [ctypes.c_void_p]
    library.MagickTrimImage.argtypes = [ctypes.c_void_p,
                                        ctypes.c_double]

    # library.MagickUniqueImageColors
    library.MagickUnsharpMaskImage.argtypes = [ctypes.c_void_p,
                                               ctypes.c_double,
                                               ctypes.c_double,
                                               ctypes.c_double,
                                               ctypes.c_double]
    # library.MagickVignetteImage
    # library.MagickWaveImage
    # library.MagickWhiteThresholdImage
    library.MagickWriteImage.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    library.MagickWriteImageFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    library.MagickWriteImages.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                          ctypes.c_int]
    library.MagickWriteImagesFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    #
    # Pixel Iterator Methods
    # http://www.imagemagick.org/api/pixel-iterator.php
    # library.ClearPixelIterator
    library.ClonePixelIterator.argtypes = [ctypes.c_void_p]
    library.ClonePixelIterator.restype = ctypes.c_void_p
    library.DestroyPixelIterator.argtypes = [ctypes.c_void_p]
    library.DestroyPixelIterator.restype = ctypes.c_void_p
    library.IsPixelIterator.argtypes = [ctypes.c_void_p]
    library.NewPixelIterator.argtypes = [ctypes.c_void_p]
    library.NewPixelIterator.restype = ctypes.c_void_p
    library.PixelClearIteratorException.argtypes = [ctypes.c_void_p]
    # library.NewPixelRegionIterator
    # library.PixelGetCurrentIteratorRow
    library.PixelGetIteratorException.argtypes = [ctypes.c_void_p,
                                                  ctypes.POINTER(ctypes.c_int)]
    library.PixelGetIteratorException.restype = c_magick_char_p
    # library.PixelGetIteratorExceptionType
    # library.PixelGetIteratorRow
    library.PixelGetNextIteratorRow.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t)
    ]
    library.PixelGetNextIteratorRow.restype = ctypes.POINTER(ctypes.c_void_p)
    # library.PixelGetPreviousIteratorRow
    # library.PixelResetIterator
    library.PixelSetFirstIteratorRow.argtypes = [ctypes.c_void_p]
    library.PixelSetIteratorRow.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t]
    # library.PixelSetLastIteratorRow
    # library.PixelSyncIterator

    #
    # Pixel Wand Methods
    # http://www.imagemagick.org/api/pixel-wand.php
    # library.ClearPixelWand
    # library.ClonePixelWand
    # library.ClonePixelWands
    library.DestroyPixelWand.argtypes = [ctypes.c_void_p]
    library.DestroyPixelWand.restype = ctypes.c_void_p
    # library.DestroyPixelWands
    library.IsPixelWandSimilar.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_double]
    library.IsPixelWand.argtypes = [ctypes.c_void_p]
    library.NewPixelWand.argtypes = []
    library.NewPixelWand.restype = ctypes.c_void_p
    # library.NewPixelWands
    library.PixelClearException.argtypes = [ctypes.c_void_p]
    library.PixelGetAlpha.argtypes = [ctypes.c_void_p]
    library.PixelGetAlpha.restype = ctypes.c_double
    library.PixelGetAlphaQuantum.argtypes = [ctypes.c_void_p]
    library.PixelGetAlphaQuantum.restype = ctypes.c_size_t
    # library.PixelGetBlack
    # library.PixelGetBlackQuantum
    library.PixelGetBlue.argtypes = [ctypes.c_void_p]
    library.PixelGetBlue.restype = ctypes.c_double
    library.PixelGetBlueQuantum.argtypes = [ctypes.c_void_p]
    library.PixelGetBlueQuantum.restype = ctypes.c_size_t
    library.PixelGetColorAsString.argtypes = [ctypes.c_void_p]
    library.PixelGetColorAsString.restype = c_magick_char_p
    library.PixelGetColorAsNormalizedString.argtypes = [ctypes.c_void_p]
    library.PixelGetColorAsNormalizedString.restype = c_magick_char_p
    library.PixelGetColorCount.argtypes = [ctypes.c_void_p]
    library.PixelGetColorCount.restype = ctypes.c_size_t
    # library.PixelGetCyan
    # library.PixelGetCyanQuantum
    library.PixelGetException.argtypes = [ctypes.c_void_p,
                                          ctypes.POINTER(ctypes.c_int)]
    library.PixelGetException.restype = c_magick_char_p
    # library.PixelGetExceptionType
    # library.PixelGetFuzz
    library.PixelGetGreen.argtypes = [ctypes.c_void_p]
    library.PixelGetGreen.restype = ctypes.c_double
    library.PixelGetGreenQuantum.argtypes = [ctypes.c_void_p]
    library.PixelGetGreenQuantum.restype = ctypes.c_size_t
    # library.PixelGetHSL
    # library.PixelGetIndex
    # library.PixelGetMagenta
    # library.PixelGetMagentaQuantum
    library.PixelGetMagickColor.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    # library.PixelGetPixel
    # library.PixelGetQuantumPacket
    # library.PixelGetQuantumPixel
    library.PixelGetRed.argtypes = [ctypes.c_void_p]
    library.PixelGetRed.restype = ctypes.c_double
    library.PixelGetRedQuantum.argtypes = [ctypes.c_void_p]
    library.PixelGetRedQuantum.restype = ctypes.c_size_t
    # library.PixelGetYellow
    # library.PixelGetYellowQuantum
    # library.PixelSetAlpha
    # library.PixelSetAlphaQuantum
    # library.PixelSetBlack
    # library.PixelSetBlackQuantum
    # library.PixelSetBlue
    # library.PixelSetBlueQuantum
    library.PixelSetColor.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    # library.PixelSetColorCount
    # library.PixelSetColorFromWand
    # library.PixelSetCyan
    # library.PixelSetCyanQuantum
    # library.PixelSetFuzz
    # library.PixelSetGreen
    # library.PixelSetGreenQuantum
    # library.PixelSetHSL
    # library.PixelSetIndex
    # library.PixelSetMagenta
    # library.PixelSetMagentaQuantum
    library.PixelSetMagickColor.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    # library.PixelSetPixelColor
    # library.PixelSetQuantumPixel
    # library.PixelSetRed
    # library.PixelSetRedQuantum
    # library.PixelSetYellow
    # library.PixelSetYellowQuantum

    # Image Vector Drawing
    # http://www.imagemagick.org/api/drawing-wand.php
    library.ClearDrawingWand.argtypes = [ctypes.c_void_p]
    library.CloneDrawingWand.argtypes = [ctypes.c_void_p]
    library.CloneDrawingWand.restype = ctypes.c_void_p
    library.DestroyDrawingWand.argtypes = [ctypes.c_void_p]
    library.DestroyDrawingWand.restype = ctypes.c_void_p
    library.DrawAffine.argtypes = [ctypes.c_void_p,  # Drawing wand
                                   ctypes.POINTER(AffineMatrix)]  # AffineMatrix
    # library.DrawAlpha
    library.DrawAnnotation.argtypes = [ctypes.c_void_p,
                                       ctypes.c_double,
                                       ctypes.c_double,
                                       ctypes.POINTER(ctypes.c_ubyte)]
    library.DrawArc.argtypes = [ctypes.c_void_p,  # wand
                                ctypes.c_double,  # sx
                                ctypes.c_double,  # sy
                                ctypes.c_double,  # ex
                                ctypes.c_double,  # ey
                                ctypes.c_double,  # sd
                                ctypes.c_double]  # ed
    library.DrawBezier.argtypes = [ctypes.c_void_p,
                                   ctypes.c_ulong,
                                   ctypes.POINTER(PointInfo)]
    library.DrawCircle.argtypes = [ctypes.c_void_p,  # wand
                                   ctypes.c_double,  # ox
                                   ctypes.c_double,  # oy
                                   ctypes.c_double,  # px
                                   ctypes.c_double]  # py
    library.DrawClearException.argtypes = [ctypes.c_void_p]
    library.DrawClearException.restype = ctypes.c_int
    # library.DrawCloneExceptionInfo
    library.DrawComposite.argtypes = [ctypes.c_void_p,  # DrawingWand wand
                                      ctypes.c_int,  # CompositeOperator
                                      ctypes.c_double,  # x
                                      ctypes.c_double,  # y
                                      ctypes.c_double,  # width
                                      ctypes.c_double,  # height
                                      ctypes.c_void_p]  # MagickWand wand
    library.DrawColor.argtypes = [ctypes.c_void_p,  # wand
                                  ctypes.c_double,  # x
                                  ctypes.c_double,  # y
                                  ctypes.c_uint]    # PaintMethod
    library.DrawComment.argtypes = [ctypes.c_void_p,  # wand
                                    ctypes.c_char_p]  # comment
    library.DrawEllipse.argtypes = [ctypes.c_void_p,  # wand
                                    ctypes.c_double,  # ox
                                    ctypes.c_double,  # oy
                                    ctypes.c_double,  # rx
                                    ctypes.c_double,  # ry
                                    ctypes.c_double,  # start
                                    ctypes.c_double]  # end
    library.DrawGetBorderColor.argtypes = [ctypes.c_void_p,  # wand
                                           ctypes.c_void_p]  # PixelWand color
    library.DrawGetClipPath.argtypes = [ctypes.c_void_p]
    library.DrawGetClipPath.restype = c_magick_char_p
    library.DrawGetClipRule.argtypes = [ctypes.c_void_p]
    library.DrawGetClipRule.restype = ctypes.c_uint
    library.DrawGetClipUnits.argtypes = [ctypes.c_void_p]
    library.DrawGetClipUnits.restype = ctypes.c_uint
    library.DrawGetException.argtypes = [ctypes.c_void_p,
                                         ctypes.POINTER(ctypes.c_int)]
    library.DrawGetException.restype = ctypes.c_char_p
    # library.DrawGetExceptionType
    library.DrawGetFillColor.argtypes = [ctypes.c_void_p,
                                         ctypes.c_void_p]
    library.DrawGetFillOpacity.argtypes = [ctypes.c_void_p]
    library.DrawGetFillOpacity.restype = ctypes.c_double
    library.DrawGetFillRule.argtypes = [ctypes.c_void_p]
    library.DrawGetFillRule.restype = ctypes.c_uint
    library.DrawGetFont.argtypes = [ctypes.c_void_p]
    library.DrawGetFont.restype = c_magick_char_p
    library.DrawGetFontFamily.argtypes = [ctypes.c_void_p]
    library.DrawGetFontFamily.restype = c_magick_char_p
    library.DrawGetFontResolution.argtypes = [ctypes.c_void_p, #wand
                               ctypes.POINTER(ctypes.c_double), # x
                               ctypes.POINTER(ctypes.c_double)] # y
    library.DrawGetFontResolution.restype = ctypes.c_uint
    library.DrawGetFontSize.argtypes = [ctypes.c_void_p]
    library.DrawGetFontSize.restype = ctypes.c_double
    library.DrawGetFontStretch.argtypes = [ctypes.c_void_p]
    library.DrawGetFontStretch.restype = ctypes.c_int
    library.DrawGetFontStyle.argtypes = [ctypes.c_void_p]
    library.DrawGetFontStyle.restype = ctypes.c_int
    library.DrawGetFontWeight.argtypes = [ctypes.c_void_p]
    library.DrawGetFontWeight.restype = ctypes.c_size_t
    library.DrawGetGravity.argtypes = [ctypes.c_void_p]
    library.DrawGetGravity.restype = ctypes.c_int
    library.DrawGetOpacity.argtypes = [ctypes.c_void_p]
    library.DrawGetOpacity.restype = ctypes.c_double
    library.DrawGetStrokeAntialias.argtypes = [ctypes.c_void_p]
    library.DrawGetStrokeAntialias.restype = ctypes.c_int
    library.DrawGetStrokeColor.argtypes = [ctypes.c_void_p,
                                           ctypes.c_void_p]
    library.DrawGetStrokeDashArray.argtypes = [ctypes.c_void_p,
                                               ctypes.POINTER(ctypes.c_size_t)]
    library.DrawGetStrokeDashArray.restype = ctypes.POINTER(ctypes.c_double)
    library.DrawGetStrokeDashOffset.argtypes = [ctypes.c_void_p]
    library.DrawGetStrokeDashOffset.restype = ctypes.c_double
    library.DrawGetStrokeLineCap.argtypes = [ctypes.c_void_p]
    library.DrawGetStrokeLineCap.restype = ctypes.c_int
    library.DrawGetStrokeLineJoin.argtypes = [ctypes.c_void_p]
    library.DrawGetStrokeLineJoin.restype = ctypes.c_int
    library.DrawGetStrokeMiterLimit.argtypes = [ctypes.c_void_p]
    library.DrawGetStrokeMiterLimit.restype = ctypes.c_size_t
    library.DrawGetStrokeOpacity.argtypes = [ctypes.c_void_p]
    library.DrawGetStrokeOpacity.restype = ctypes.c_double
    library.DrawGetStrokeWidth.argtypes = [ctypes.c_void_p]
    library.DrawGetStrokeWidth.restype = ctypes.c_double
    library.DrawGetTextAlignment.argtypes = [ctypes.c_void_p]
    library.DrawGetTextAlignment.restype = ctypes.c_int
    library.DrawGetTextAntialias.argtypes = [ctypes.c_void_p]
    library.DrawGetTextAntialias.restype = ctypes.c_int
    library.DrawGetTextDecoration.argtypes = [ctypes.c_void_p]
    library.DrawGetTextDecoration.restype = ctypes.c_int
    try:
        library.DrawGetTextDirection.argtypes = [ctypes.c_void_p]
        library.DrawGetTextDirection.restype = ctypes.c_int
    except AttributeError:
        library.DrawGetTextDirection = None
    library.DrawGetTextEncoding.argtypes = [ctypes.c_void_p]
    library.DrawGetTextEncoding.restype = c_magick_char_p
    library.DrawGetTextKerning.argtypes = [ctypes.c_void_p]
    library.DrawGetTextKerning.restype = ctypes.c_double
    try:
        library.DrawGetTextInterlineSpacing.argtypes = [ctypes.c_void_p]
        library.DrawGetTextInterlineSpacing.restype = ctypes.c_double
    except AttributeError:
        library.DrawGetTextInterlineSpacing = None
    library.DrawGetTextInterwordSpacing.argtypes = [ctypes.c_void_p]
    library.DrawGetTextInterwordSpacing.restype = ctypes.c_double
    library.DrawGetVectorGraphics.argtypes = [ctypes.c_void_p]
    library.DrawGetVectorGraphics.restype = c_magick_char_p
    library.DrawGetTextUnderColor.argtypes = [ctypes.c_void_p,
                                              ctypes.c_void_p]
    library.DrawLine.argtypes = [ctypes.c_void_p,
                                 ctypes.c_double,
                                 ctypes.c_double,
                                 ctypes.c_double,
                                 ctypes.c_double]
    library.DrawMatte.argtypes = [ctypes.c_void_p,  # wand
                                  ctypes.c_double,  # x
                                  ctypes.c_double,  # y
                                  ctypes.c_uint]  # PaintMethod
    library.DrawPathClose.argtypes = [ctypes.c_void_p]
    library.DrawPathCurveToAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                                ctypes.c_double,  # x1
                                                ctypes.c_double,  # y1
                                                ctypes.c_double,  # x2
                                                ctypes.c_double,  # y2
                                                ctypes.c_double,  # x
                                                ctypes.c_double]  # y
    library.DrawPathCurveToRelative.argtypes = [ctypes.c_void_p,  # wand
                                                ctypes.c_double,  # x1
                                                ctypes.c_double,  # y1
                                                ctypes.c_double,  # x2
                                                ctypes.c_double,  # y2
                                                ctypes.c_double,  # x
                                                ctypes.c_double]  # y
    library.DrawPathCurveToQuadraticBezierAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                                               ctypes.c_double,  # x1
                                                               ctypes.c_double,  # y1
                                                               ctypes.c_double,  # x
                                                               ctypes.c_double]  # y
    library.DrawPathCurveToQuadraticBezierRelative.argtypes = [ctypes.c_void_p,  # wand
                                                               ctypes.c_double,  # x1
                                                               ctypes.c_double,  # y1
                                                               ctypes.c_double,  # x
                                                               ctypes.c_double]  # y
    library.DrawPathCurveToQuadraticBezierSmoothAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                                                     ctypes.c_double,  # x
                                                                     ctypes.c_double]  # y
    library.DrawPathCurveToQuadraticBezierSmoothRelative.argtypes = [ctypes.c_void_p,  # wand
                                                                     ctypes.c_double,  # x
                                                                     ctypes.c_double]  # y
    library.DrawPathCurveToSmoothAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                                      ctypes.c_double,  # x2
                                                      ctypes.c_double,  # y2
                                                      ctypes.c_double,  # x
                                                      ctypes.c_double]  # y
    library.DrawPathCurveToSmoothRelative.argtypes = [ctypes.c_void_p,  # wand
                                                      ctypes.c_double,  # x2
                                                      ctypes.c_double,  # y2
                                                      ctypes.c_double,  # x
                                                      ctypes.c_double]  # y
    library.DrawPathEllipticArcAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                                    ctypes.c_double,  # rx
                                                    ctypes.c_double,  # ry
                                                    ctypes.c_double,  # rotation
                                                    ctypes.c_uint,  # arc_flag
                                                    ctypes.c_uint,  # sweep_flag
                                                    ctypes.c_double,  # x
                                                    ctypes.c_double]  # y
    library.DrawPathEllipticArcRelative.argtypes = [ctypes.c_void_p,  # wand
                                                    ctypes.c_double,  # rx
                                                    ctypes.c_double,  # ry
                                                    ctypes.c_double,  # rotation
                                                    ctypes.c_uint,  # arc_flag
                                                    ctypes.c_uint,  # sweep_flag
                                                    ctypes.c_double,  # x
                                                    ctypes.c_double]  # y
    library.DrawPathFinish.argtypes = [ctypes.c_void_p]
    library.DrawPathLineToAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                               ctypes.c_double,  # x
                                               ctypes.c_double]  # y
    library.DrawPathLineToRelative.argtypes = [ctypes.c_void_p,  # wand
                                               ctypes.c_double,  # x
                                               ctypes.c_double]  # y
    library.DrawPathLineToHorizontalAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                                         ctypes.c_double]  # x
    library.DrawPathLineToHorizontalRelative.argtypes = [ctypes.c_void_p,  # wand
                                                         ctypes.c_double]  # x
    library.DrawPathLineToVerticalAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                                       ctypes.c_double]  # y
    library.DrawPathLineToVerticalRelative.argtypes = [ctypes.c_void_p,  # wand
                                                       ctypes.c_double]  # y
    library.DrawPathMoveToAbsolute.argtypes = [ctypes.c_void_p,  # wand
                                               ctypes.c_double,  # x
                                               ctypes.c_double]  # y
    library.DrawPathMoveToRelative.argtypes = [ctypes.c_void_p,  # wand
                                               ctypes.c_double,  # x
                                               ctypes.c_double]  # y
    library.DrawPathStart.argtypes = [ctypes.c_void_p]
    library.DrawPoint.argtypes = [ctypes.c_void_p,  # wand
                                  ctypes.c_double,  # x
                                  ctypes.c_double]  # y
    library.DrawPolygon.argtypes = [ctypes.c_void_p,
                                    ctypes.c_ulong,
                                    ctypes.POINTER(PointInfo)]
    library.DrawPolyline.argtypes = [ctypes.c_void_p,
                                     ctypes.c_ulong,
                                     ctypes.POINTER(PointInfo)]
    library.DrawPopClipPath.argtypes = [ctypes.c_void_p]
    library.DrawPopDefs.argtypes = [ctypes.c_void_p]
    library.DrawPopPattern.argtypes = [ctypes.c_void_p]
    library.DrawPushClipPath.argtypes = [ctypes.c_void_p,  # wand
                                         ctypes.c_char_p]  # clip_mask_id
    library.DrawPushDefs.argtypes = [ctypes.c_void_p]
    library.DrawPushPattern.argtypes = [ctypes.c_void_p,  # wand
                                        ctypes.c_char_p,  # clip_mask_id
                                        ctypes.c_double,  # x
                                        ctypes.c_double,  # y
                                        ctypes.c_double,  # width
                                        ctypes.c_double]  # height
    library.DrawRectangle.argtypes = [ctypes.c_void_p,
                                      ctypes.c_double,
                                      ctypes.c_double,
                                      ctypes.c_double,
                                      ctypes.c_double]
    library.DrawResetVectorGraphics.argtypes = [ctypes.c_void_p]
    library.DrawRotate.argtypes = [ctypes.c_void_p,  # wand
                                   ctypes.c_double]  # degree
    library.DrawRoundRectangle.argtypes = [ctypes.c_void_p,  # wand
                                           ctypes.c_double,  # x1
                                           ctypes.c_double,  # y1
                                           ctypes.c_double,  # x2
                                           ctypes.c_double,  # y2
                                           ctypes.c_double,  # rx
                                           ctypes.c_double]  # ry
    library.DrawScale.argtypes = [ctypes.c_void_p,  # wand
                                  ctypes.c_double,  # x
                                  ctypes.c_double]  # y
    library.DrawSetBorderColor.argtypes = [ctypes.c_void_p,  # wand
                                           ctypes.c_void_p]  # PixelWand color
    library.DrawSetClipPath.argtypes = [ctypes.c_void_p,  # wand
                                        ctypes.c_char_p]  # clip_mask
    library.DrawSetClipPath.restype = ctypes.c_int
    library.DrawSetClipRule.argtypes = [ctypes.c_void_p,  # wand
                                        ctypes.c_uint]  # FillRule
    library.DrawSetClipUnits.argtypes = [ctypes.c_void_p,  # wand
                                         ctypes.c_uint]  # ClipPathUnits
    library.DrawSetFillColor.argtypes = [ctypes.c_void_p,
                                         ctypes.c_void_p]
    library.DrawSetFillOpacity.argtypes = [ctypes.c_void_p,
                                           ctypes.c_double]
    library.DrawSetFillPatternURL.argtypes = [ctypes.c_void_p,  # wand
                                              ctypes.c_char_p]  # fill_url
    library.DrawSetFillPatternURL.restype = ctypes.c_uint
    library.DrawSetFillRule.argtypes = [ctypes.c_void_p,
                                        ctypes.c_uint]
    library.DrawSetFont.argtypes = [ctypes.c_void_p,
                                    ctypes.c_char_p]
    library.DrawSetFontFamily.argtypes = [ctypes.c_void_p,  # wand
                                          ctypes.c_char_p]  # font_family
    library.DrawSetFontFamily.restype = ctypes.c_uint

    library.DrawSetFontResolution.argtypes = [ctypes.c_void_p,  # wand
                                              ctypes.c_double,  # x
                                              ctypes.c_double]  # y
    library.DrawSetFontResolution.restype = ctypes.c_uint
    library.DrawSetFontSize.argtypes = [ctypes.c_void_p,
                                        ctypes.c_double]
    library.DrawSetFontStretch.argtypes = [ctypes.c_void_p,  # wand
                                           ctypes.c_int]  # font_stretch
    library.DrawSetFontStyle.argtypes = [ctypes.c_void_p,  # wand
                                         ctypes.c_int]  # style
    library.DrawSetFontWeight.argtypes = [ctypes.c_void_p,  # wand
                                          ctypes.c_size_t]  # font_weight
    library.DrawSetOpacity.argtypes = [ctypes.c_void_p, ctypes.c_double]
    library.DrawSetGravity.argtypes = [ctypes.c_void_p,
                                       ctypes.c_int]
    library.DrawSetStrokeAntialias.argtypes = [ctypes.c_void_p,  # wand
                                               ctypes.c_int]  # stroke_antialias
    library.DrawSetStrokeColor.argtypes = [ctypes.c_void_p,
                                           ctypes.c_void_p]
    library.DrawSetStrokeDashArray.argtypes = [ctypes.c_void_p,  # wand
                                               ctypes.c_size_t,  # number_elements
                                               ctypes.POINTER(ctypes.c_double)]
    library.DrawSetStrokeDashOffset.argtypes = [ctypes.c_void_p,  # wand
                                                ctypes.c_double]  # dash_offset
    library.DrawSetStrokeLineCap.argtypes = [ctypes.c_void_p,  # wand
                                             ctypes.c_int]  # linecap
    library.DrawSetStrokeLineJoin.argtypes = [ctypes.c_void_p,  # wand
                                              ctypes.c_int]  # linejoin
    library.DrawSetStrokeMiterLimit.argtypes = [ctypes.c_void_p,  # wand
                                                ctypes.c_size_t]  # miterlimit
    library.DrawSetStrokeOpacity.argtypes = [ctypes.c_void_p,  # wand
                                             ctypes.c_double]  # stroke_opacity
    library.DrawSetStrokePatternURL.argtypes = [ctypes.c_void_p,  # wand
                                                ctypes.c_char_p]  # fill_url
    library.DrawSetStrokePatternURL.restype = ctypes.c_uint
    library.DrawSetStrokeWidth.argtypes = [ctypes.c_void_p,
                                           ctypes.c_double]
    library.DrawSetTextAlignment.argtypes = [ctypes.c_void_p,
                                             ctypes.c_int]
    library.DrawSetTextAntialias.argtypes = [ctypes.c_void_p,
                                             ctypes.c_int]
    library.DrawSetTextDecoration.argtypes = [ctypes.c_void_p,
                                              ctypes.c_int]
    try:
        library.DrawSetTextDirection.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_int]
    except AttributeError:
        library.DrawSetTextDirection = None

    library.DrawSetTextEncoding.argtypes = [ctypes.c_void_p,
                                            ctypes.c_char_p]
    try:
        library.DrawSetTextInterlineSpacing.argtypes = [ctypes.c_void_p,
                                                        ctypes.c_double]
    except AttributeError:
        library.DrawSetTextInterlineSpacing = None
    library.DrawSetTextInterwordSpacing.argtypes = [ctypes.c_void_p,
                                                    ctypes.c_double]
    library.DrawSetTextKerning.argtypes = [ctypes.c_void_p,
                                           ctypes.c_double]
    library.DrawSetTextUnderColor.argtypes = [ctypes.c_void_p,
                                              ctypes.c_void_p]
    library.DrawSetVectorGraphics.argtypes = [ctypes.c_void_p,
                                              ctypes.c_char_p]
    library.DrawSetViewbox.argtypes = [ctypes.c_void_p,  # wand
                                       ctypes.c_ssize_t,  # x1
                                       ctypes.c_ssize_t,  # y1
                                       ctypes.c_ssize_t,  # x2
                                       ctypes.c_ssize_t]  # y2
    library.DrawSkewX.argtypes = [ctypes.c_void_p,  # wand
                                  ctypes.c_double]  # degree
    library.DrawSkewY.argtypes = [ctypes.c_void_p,  # wand
                                  ctypes.c_double]  # degree
    library.DrawTranslate.argtypes = [ctypes.c_void_p,  # wand
                                      ctypes.c_double,  # x
                                      ctypes.c_double]  # y
    library.IsDrawingWand.argtypes = [ctypes.c_void_p]
    library.IsDrawingWand.restype = ctypes.c_int
    library.NewDrawingWand.restype = ctypes.c_void_p
    # library.PeekDrawingWand
    library.PopDrawingWand.argtypes = [ctypes.c_void_p]
    library.PopDrawingWand.restype = ctypes.c_uint
    library.PushDrawingWand.argtypes = [ctypes.c_void_p]
    library.PushDrawingWand.restype = ctypes.c_uint

except AttributeError:
    raise ImportError('MagickWand shared library not found or incompatible\n'
                      'Original exception was raised in:\n' +
                      traceback.format_exc())



#: (:class:`ctypes.CDLL`) The C standard library.
libc = None

if platform.system() == 'Windows':
    libc = ctypes.CDLL(ctypes.util.find_msvcrt())
else:
    if platform.system() == 'Darwin':
        libc = ctypes.cdll.LoadLibrary('libc.dylib')
    elif platform.system() == 'FreeBSD':
        libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
    else:
        libc = ctypes.cdll.LoadLibrary('libc.so.6')
    libc.fdopen.argtypes = [ctypes.c_int, ctypes.c_char_p]
    libc.fdopen.restype = ctypes.c_void_p
    libc.fflush.argtypes = [ctypes.c_void_p]

libc.free.argtypes = [ctypes.c_void_p]
