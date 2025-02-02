import numpy
import librosa
import argparse
import numpy as np
import moviepy.editor as mpy
import random
import torch

from tqdm import tqdm
from pytorch_pretrained_biggan import (BigGAN, one_hot_from_names, truncated_noise_sample,
                                       save_as_images, display_in_terminal)
from numpy import (amin, amax, ravel, asarray, arange, ones, newaxis,
                   transpose, iscomplexobj, uint8, issubdtype, array)

try:
    from PIL import Image, ImageFilter
except ImportError:
    import Image
    import ImageFilter


if not hasattr(Image, 'frombytes'):
    Image.frombytes = Image.fromstring

__all__ = ['fromimage', 'toimage', 'imsave', 'imread', 'bytescale',
           'imrotate', 'imresize', 'imshow', 'imfilter']


@numpy.deprecate(message="`bytescale` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.2.0.")
def bytescale(data, cmin=None, cmax=None, high=255, low=0):
    """
    Byte scales an array (image).
    Byte scaling means converting the input image to uint8 dtype and scaling
    the range to ``(low, high)`` (default 0-255).
    If the input image already has dtype uint8, no scaling is done.
    This function is only available if Python Imaging Library (PIL) is installed.
    Parameters
    ----------
    data : ndarray
        PIL image data array.
    cmin : scalar, optional
        Bias scaling of small values. Default is ``data.min()``.
    cmax : scalar, optional
        Bias scaling of large values. Default is ``data.max()``.
    high : scalar, optional
        Scale max value to `high`.  Default is 255.
    low : scalar, optional
        Scale min value to `low`.  Default is 0.
    Returns
    -------
    img_array : uint8 ndarray
        The byte-scaled array.
    Examples
    --------
    >>> from scipy.misc import bytescale
    >>> img = np.array([[ 91.06794177,   3.39058326,  84.4221549 ],
    ...                 [ 73.88003259,  80.91433048,   4.88878881],
    ...                 [ 51.53875334,  34.45808177,  27.5873488 ]])
    >>> bytescale(img)
    array([[255,   0, 236],
           [205, 225,   4],
           [140,  90,  70]], dtype=uint8)
    >>> bytescale(img, high=200, low=100)
    array([[200, 100, 192],
           [180, 188, 102],
           [155, 135, 128]], dtype=uint8)
    >>> bytescale(img, cmin=0, cmax=255)
    array([[91,  3, 84],
           [74, 81,  5],
           [52, 34, 28]], dtype=uint8)
    """
    if data.dtype == uint8:
        return data

    if high > 255:
        raise ValueError("`high` should be less than or equal to 255.")
    if low < 0:
        raise ValueError("`low` should be greater than or equal to 0.")
    if high < low:
        raise ValueError("`high` should be greater than or equal to `low`.")

    if cmin is None:
        cmin = data.min()
    if cmax is None:
        cmax = data.max()

    cscale = cmax - cmin
    if cscale < 0:
        raise ValueError("`cmax` should be larger than `cmin`.")
    elif cscale == 0:
        cscale = 1

    scale = float(high - low) / cscale
    bytedata = (data - cmin) * scale + low
    return (bytedata.clip(low, high) + 0.5).astype(uint8)


@numpy.deprecate(message="`imread` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.2.0.\n"
                         "Use ``imageio.imread`` instead.")
def imread(name, flatten=False, mode=None):
    """
    Read an image from a file as an array.
    This function is only available if Python Imaging Library (PIL) is installed.
    Parameters
    ----------
    name : str or file object
        The file name or file object to be read.
    flatten : bool, optional
        If True, flattens the color layers into a single gray-scale layer.
    mode : str, optional
        Mode to convert image to, e.g. ``'RGB'``.  See the Notes for more
        details.
    Returns
    -------
    imread : ndarray
        The array obtained by reading the image.
    Notes
    -----
    `imread` uses the Python Imaging Library (PIL) to read an image.
    The following notes are from the PIL documentation.
    `mode` can be one of the following strings:
    * 'L' (8-bit pixels, black and white)
    * 'P' (8-bit pixels, mapped to any other mode using a color palette)
    * 'RGB' (3x8-bit pixels, true color)
    * 'RGBA' (4x8-bit pixels, true color with transparency mask)
    * 'CMYK' (4x8-bit pixels, color separation)
    * 'YCbCr' (3x8-bit pixels, color video format)
    * 'I' (32-bit signed integer pixels)
    * 'F' (32-bit floating point pixels)
    PIL also provides limited support for a few special modes, including
    'LA' ('L' with alpha), 'RGBX' (true color with padding) and 'RGBa'
    (true color with premultiplied alpha).
    When translating a color image to black and white (mode 'L', 'I' or
    'F'), the library uses the ITU-R 601-2 luma transform::
        L = R * 299/1000 + G * 587/1000 + B * 114/1000
    When `flatten` is True, the image is converted using mode 'F'.
    When `mode` is not None and `flatten` is True, the image is first
    converted according to `mode`, and the result is then flattened using
    mode 'F'.
    """

    im = Image.open(name)
    return fromimage(im, flatten=flatten, mode=mode)


@numpy.deprecate(message="`imsave` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.2.0.\n"
                         "Use ``imageio.imwrite`` instead.")
def imsave(name, arr, format=None):
    """
    Save an array as an image.
    This function is only available if Python Imaging Library (PIL) is installed.
    .. warning::
        This function uses `bytescale` under the hood to rescale images to use
        the full (0, 255) range if ``mode`` is one of ``None, 'L', 'P', 'l'``.
        It will also cast data for 2-D images to ``uint32`` for ``mode=None``
        (which is the default).
    Parameters
    ----------
    name : str or file object
        Output file name or file object.
    arr : ndarray, MxN or MxNx3 or MxNx4
        Array containing image values.  If the shape is ``MxN``, the array
        represents a grey-level image.  Shape ``MxNx3`` stores the red, green
        and blue bands along the last dimension.  An alpha layer may be
        included, specified as the last colour band of an ``MxNx4`` array.
    format : str
        Image format. If omitted, the format to use is determined from the
        file name extension. If a file object was used instead of a file name,
        this parameter should always be used.
    Examples
    --------
    Construct an array of gradient intensity values and save to file:
    >>> from scipy.misc import imsave
    >>> x = np.zeros((255, 255))
    >>> x = np.zeros((255, 255), dtype=np.uint8)
    >>> x[:] = np.arange(255)
    >>> imsave('gradient.png', x)
    Construct an array with three colour bands (R, G, B) and store to file:
    >>> rgb = np.zeros((255, 255, 3), dtype=np.uint8)
    >>> rgb[..., 0] = np.arange(255)
    >>> rgb[..., 1] = 55
    >>> rgb[..., 2] = 1 - np.arange(255)
    >>> imsave('rgb_gradient.png', rgb)
    """
    im = toimage(arr, channel_axis=2)
    if format is None:
        im.save(name)
    else:
        im.save(name, format)
    return


@numpy.deprecate(message="`fromimage` is deprecated in SciPy 1.0.0. "
                         "and will be removed in 1.2.0.\n"
                         "Use ``np.asarray(im)`` instead.")
def fromimage(im, flatten=False, mode=None):
    """
    Return a copy of a PIL image as a numpy array.
    This function is only available if Python Imaging Library (PIL) is installed.
    Parameters
    ----------
    im : PIL image
        Input image.
    flatten : bool
        If true, convert the output to grey-scale.
    mode : str, optional
        Mode to convert image to, e.g. ``'RGB'``.  See the Notes of the
        `imread` docstring for more details.
    Returns
    -------
    fromimage : ndarray
        The different colour bands/channels are stored in the
        third dimension, such that a grey-image is MxN, an
        RGB-image MxNx3 and an RGBA-image MxNx4.
    """
    if not Image.isImageType(im):
        raise TypeError("Input is not a PIL image.")

    if mode is not None:
        if mode != im.mode:
            im = im.convert(mode)
    elif im.mode == 'P':
        # Mode 'P' means there is an indexed "palette".  If we leave the mode
        # as 'P', then when we do `a = array(im)` below, `a` will be a 2-D
        # containing the indices into the palette, and not a 3-D array
        # containing the RGB or RGBA values.
        if 'transparency' in im.info:
            im = im.convert('RGBA')
        else:
            im = im.convert('RGB')

    if flatten:
        im = im.convert('F')
    elif im.mode == '1':
        # Workaround for crash in PIL. When im is 1-bit, the call array(im)
        # can cause a seg. fault, or generate garbage. See
        # https://github.com/scipy/scipy/issues/2138 and
        # https://github.com/python-pillow/Pillow/issues/350.
        #
        # This converts im from a 1-bit image to an 8-bit image.
        im = im.convert('L')

    a = array(im)
    return a


_errstr = "Mode is unknown or incompatible with input array shape."


@numpy.deprecate(message="`toimage` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.2.0.\n"
            "Use Pillow's ``Image.fromarray`` directly instead.")
def toimage(arr, high=255, low=0, cmin=None, cmax=None, pal=None,
            mode=None, channel_axis=None):
    """Takes a numpy array and returns a PIL image.
    This function is only available if Python Imaging Library (PIL) is installed.
    The mode of the PIL image depends on the array shape and the `pal` and
    `mode` keywords.
    For 2-D arrays, if `pal` is a valid (N,3) byte-array giving the RGB values
    (from 0 to 255) then ``mode='P'``, otherwise ``mode='L'``, unless mode
    is given as 'F' or 'I' in which case a float and/or integer array is made.
    .. warning::
        This function uses `bytescale` under the hood to rescale images to use
        the full (0, 255) range if ``mode`` is one of ``None, 'L', 'P', 'l'``.
        It will also cast data for 2-D images to ``uint32`` for ``mode=None``
        (which is the default).
    Notes
    -----
    For 3-D arrays, the `channel_axis` argument tells which dimension of the
    array holds the channel data.
    For 3-D arrays if one of the dimensions is 3, the mode is 'RGB'
    by default or 'YCbCr' if selected.
    The numpy array must be either 2 dimensional or 3 dimensional.
    """
    data = asarray(arr)
    if iscomplexobj(data):
        raise ValueError("Cannot convert a complex-valued array.")
    shape = list(data.shape)
    valid = len(shape) == 2 or ((len(shape) == 3) and
                                ((3 in shape) or (4 in shape)))
    if not valid:
        raise ValueError("'arr' does not have a suitable array shape for "
                         "any mode.")
    if len(shape) == 2:
        shape = (shape[1], shape[0])  # columns show up first
        if mode == 'F':
            data32 = data.astype(numpy.float32)
            image = Image.frombytes(mode, shape, data32.tostring())
            return image
        if mode in [None, 'L', 'P']:
            bytedata = bytescale(data, high=high, low=low,
                                 cmin=cmin, cmax=cmax)
            image = Image.frombytes('L', shape, bytedata.tostring())
            if pal is not None:
                image.putpalette(asarray(pal, dtype=uint8).tostring())
                # Becomes a mode='P' automagically.
            elif mode == 'P':  # default gray-scale
                pal = (arange(0, 256, 1, dtype=uint8)[:, newaxis] *
                       ones((3,), dtype=uint8)[newaxis, :])
                image.putpalette(asarray(pal, dtype=uint8).tostring())
            return image
        if mode == '1':  # high input gives threshold for 1
            bytedata = (data > high)
            image = Image.frombytes('1', shape, bytedata.tostring())
            return image
        if cmin is None:
            cmin = amin(ravel(data))
        if cmax is None:
            cmax = amax(ravel(data))
        data = (data*1.0 - cmin)*(high - low)/(cmax - cmin) + low
        if mode == 'I':
            data32 = data.astype(numpy.uint32)
            image = Image.frombytes(mode, shape, data32.tostring())
        else:
            raise ValueError(_errstr)
        return image

    # if here then 3-d array with a 3 or a 4 in the shape length.
    # Check for 3 in datacube shape --- 'RGB' or 'YCbCr'
    if channel_axis is None:
        if (3 in shape):
            ca = numpy.flatnonzero(asarray(shape) == 3)[0]
        else:
            ca = numpy.flatnonzero(asarray(shape) == 4)
            if len(ca):
                ca = ca[0]
            else:
                raise ValueError("Could not find channel dimension.")
    else:
        ca = channel_axis

    numch = shape[ca]
    if numch not in [3, 4]:
        raise ValueError("Channel axis dimension is not valid.")

    bytedata = bytescale(data, high=high, low=low, cmin=cmin, cmax=cmax)
    if ca == 2:
        strdata = bytedata.tostring()
        shape = (shape[1], shape[0])
    elif ca == 1:
        strdata = transpose(bytedata, (0, 2, 1)).tostring()
        shape = (shape[2], shape[0])
    elif ca == 0:
        strdata = transpose(bytedata, (1, 2, 0)).tostring()
        shape = (shape[2], shape[1])
    if mode is None:
        if numch == 3:
            mode = 'RGB'
        else:
            mode = 'RGBA'

    if mode not in ['RGB', 'RGBA', 'YCbCr', 'CMYK']:
        raise ValueError(_errstr)

    if mode in ['RGB', 'YCbCr']:
        if numch != 3:
            raise ValueError("Invalid array shape for mode.")
    if mode in ['RGBA', 'CMYK']:
        if numch != 4:
            raise ValueError("Invalid array shape for mode.")

    # Here we know data and mode is correct
    image = Image.frombytes(mode, shape, strdata)
    return image


@numpy.deprecate(message="`imrotate` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.2.0.\n"
                         "Use ``skimage.transform.rotate`` instead.")
def imrotate(arr, angle, interp='bilinear'):
    """
    Rotate an image counter-clockwise by angle degrees.
    This function is only available if Python Imaging Library (PIL) is installed.
    .. warning::
        This function uses `bytescale` under the hood to rescale images to use
        the full (0, 255) range if ``mode`` is one of ``None, 'L', 'P', 'l'``.
        It will also cast data for 2-D images to ``uint32`` for ``mode=None``
        (which is the default).
    Parameters
    ----------
    arr : ndarray
        Input array of image to be rotated.
    angle : float
        The angle of rotation.
    interp : str, optional
        Interpolation
        - 'nearest' :  for nearest neighbor
        - 'bilinear' : for bilinear
        - 'lanczos' : for lanczos
        - 'cubic' : for bicubic
        - 'bicubic' : for bicubic
    Returns
    -------
    imrotate : ndarray
        The rotated array of image.
    """
    arr = asarray(arr)
    func = {'nearest': 0, 'lanczos': 1, 'bilinear': 2, 'bicubic': 3, 'cubic': 3}
    im = toimage(arr)
    im = im.rotate(angle, resample=func[interp])
    return fromimage(im)


@numpy.deprecate(message="`imshow` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.2.0.\n"
                         "Use ``matplotlib.pyplot.imshow`` instead.")
def imshow(arr):
    """
    Simple showing of an image through an external viewer.
    This function is only available if Python Imaging Library (PIL) is installed.
    Uses the image viewer specified by the environment variable
    SCIPY_PIL_IMAGE_VIEWER, or if that is not defined then `see`,
    to view a temporary file generated from array data.
    .. warning::
        This function uses `bytescale` under the hood to rescale images to use
        the full (0, 255) range if ``mode`` is one of ``None, 'L', 'P', 'l'``.
        It will also cast data for 2-D images to ``uint32`` for ``mode=None``
        (which is the default).
    Parameters
    ----------
    arr : ndarray
        Array of image data to show.
    Returns
    -------
    None
    Examples
    --------
    >>> a = np.tile(np.arange(255), (255,1))
    >>> from scipy import misc
    >>> misc.imshow(a)
    """
    im = toimage(arr)
    fnum, fname = tempfile.mkstemp('.png')
    try:
        im.save(fname)
    except Exception:
        raise RuntimeError("Error saving temporary image data.")

    import os
    os.close(fnum)

    cmd = os.environ.get('SCIPY_PIL_IMAGE_VIEWER', 'see')
    status = os.system("%s %s" % (cmd, fname))

    os.unlink(fname)
    if status != 0:
        raise RuntimeError('Could not execute image viewer.')


@numpy.deprecate(message="`imresize` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.3.0.\n"
                         "Use Pillow instead: ``numpy.array(Image.fromarray(arr).resize())``.")
def imresize(arr, size, interp='bilinear', mode=None):
    """
    Resize an image.
    This function is only available if Python Imaging Library (PIL) is installed.
    .. warning::
        This function uses `bytescale` under the hood to rescale images to use
        the full (0, 255) range if ``mode`` is one of ``None, 'L', 'P', 'l'``.
        It will also cast data for 2-D images to ``uint32`` for ``mode=None``
        (which is the default).
    Parameters
    ----------
    arr : ndarray
        The array of image to be resized.
    size : int, float or tuple
        * int   - Percentage of current size.
        * float - Fraction of current size.
        * tuple - Size of the output image (height, width).
    interp : str, optional
        Interpolation to use for re-sizing ('nearest', 'lanczos', 'bilinear',
        'bicubic' or 'cubic').
    mode : str, optional
        The PIL image mode ('P', 'L', etc.) to convert `arr` before resizing.
        If ``mode=None`` (the default), 2-D images will be treated like
        ``mode='L'``, i.e. casting to long integer.  For 3-D and 4-D arrays,
        `mode` will be set to ``'RGB'`` and ``'RGBA'`` respectively.
    Returns
    -------
    imresize : ndarray
        The resized array of image.
    See Also
    --------
    toimage : Implicitly used to convert `arr` according to `mode`.
    scipy.ndimage.zoom : More generic implementation that does not use PIL.
    """
    im = toimage(arr, mode=mode)
    ts = type(size)
    if issubdtype(ts, numpy.signedinteger):
        percent = size / 100.0
        size = tuple((array(im.size)*percent).astype(int))
    elif issubdtype(type(size), numpy.floating):
        size = tuple((array(im.size)*size).astype(int))
    else:
        size = (size[1], size[0])
    func = {'nearest': 0, 'lanczos': 1, 'bilinear': 2, 'bicubic': 3, 'cubic': 3}
    imnew = im.resize(size, resample=func[interp])
    return fromimage(imnew)


@numpy.deprecate(message="`imfilter` is deprecated in SciPy 1.0.0, "
                         "and will be removed in 1.2.0.\n"
                         "Use Pillow filtering functionality directly.")
def imfilter(arr, ftype):
    """
    Simple filtering of an image.
    This function is only available if Python Imaging Library (PIL) is installed.
    .. warning::
        This function uses `bytescale` under the hood to rescale images to use
        the full (0, 255) range if ``mode`` is one of ``None, 'L', 'P', 'l'``.
        It will also cast data for 2-D images to ``uint32`` for ``mode=None``
        (which is the default).
    Parameters
    ----------
    arr : ndarray
        The array of Image in which the filter is to be applied.
    ftype : str
        The filter that has to be applied. Legal values are:
        'blur', 'contour', 'detail', 'edge_enhance', 'edge_enhance_more',
        'emboss', 'find_edges', 'smooth', 'smooth_more', 'sharpen'.
    Returns
    -------
    imfilter : ndarray
        The array with filter applied.
    Raises
    ------
    ValueError
        *Unknown filter type.*  If the filter you are trying
        to apply is unsupported.
    """
    _tdict = {'blur': ImageFilter.BLUR,
              'contour': ImageFilter.CONTOUR,
              'detail': ImageFilter.DETAIL,
              'edge_enhance': ImageFilter.EDGE_ENHANCE,
              'edge_enhance_more': ImageFilter.EDGE_ENHANCE_MORE,
              'emboss': ImageFilter.EMBOSS,
              'find_edges': ImageFilter.FIND_EDGES,
              'smooth': ImageFilter.SMOOTH,
              'smooth_more': ImageFilter.SMOOTH_MORE,
              'sharpen': ImageFilter.SHARPEN
              }

    im = toimage(arr)
    if ftype not in _tdict:
        raise ValueError("Unknown filter type.")
    return fromimage(im.filter(_tdict[ftype]))
#get input arguments
parser = argparse.ArgumentParser()
parser.add_argument("--song",required=True)
parser.add_argument("--resolution", default='512')
parser.add_argument("--duration", type=int)
parser.add_argument("--pitch_sensitivity", type=int, default=220)
parser.add_argument("--tempo_sensitivity", type=float, default=0.25)
parser.add_argument("--depth", type=float, default=1)
parser.add_argument("--classes", nargs='+', type=int)
parser.add_argument("--num_classes", type=int, default=12)
parser.add_argument("--sort_classes_by_power", type=int, default=0)
parser.add_argument("--jitter", type=float, default=0.5)
parser.add_argument("--frame_length", type=int, default=512)
parser.add_argument("--truncation", type=float, default=1)
parser.add_argument("--smooth_factor", type=int, default=20)
parser.add_argument("--batch_size", type=int, default=30)
parser.add_argument("--use_previous_classes", type=int, default=0)
parser.add_argument("--use_previous_vectors", type=int, default=0)
parser.add_argument("--output_file", default="output.mp4")
args = parser.parse_args()


#read song
if args.song:
    song=args.song
    print('\nReading audio \n')
    y, sr = librosa.load(song)
else:
    raise ValueError("you must enter an audio file name in the --song argument")

#set model name based on resolution
model_name='biggan-deep-' + args.resolution

frame_length=args.frame_length

#set pitch sensitivity
pitch_sensitivity=(300-args.pitch_sensitivity) * 512 / frame_length

#set tempo sensitivity
tempo_sensitivity=args.tempo_sensitivity * frame_length / 512

#set depth
depth=args.depth

#set number of classes  
num_classes=args.num_classes

#set sort_classes_by_power    
sort_classes_by_power=args.sort_classes_by_power

#set jitter
jitter=args.jitter
    
#set truncation
truncation=args.truncation

#set batch size  
batch_size=args.batch_size

#set use_previous_classes
use_previous_vectors=args.use_previous_vectors

#set use_previous_vectors
use_previous_classes=args.use_previous_classes
    
#set output name
outname=args.output_file

#set smooth factor
if args.smooth_factor > 1:
    smooth_factor=int(args.smooth_factor * 512 / frame_length)
else:
    smooth_factor=args.smooth_factor

#set duration  
if args.duration:
    seconds=args.duration
    frame_lim=int(np.floor(seconds*22050/frame_length/batch_size))
else:
    frame_lim=int(np.floor(len(y)/sr*22050/frame_length/batch_size))
    
    


# Load pre-trained model
model = BigGAN.from_pretrained(model_name)

#set device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


########################################
########################################
########################################
########################################
########################################


#create spectrogram
spec = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128,fmax=8000, hop_length=frame_length)

#get mean power at each time point
specm=np.mean(spec,axis=0)

#compute power gradient across time points
gradm=np.gradient(specm)

#set max to 1
gradm=gradm/np.max(gradm)

#set negative gradient time points to zero 
gradm = gradm.clip(min=0)
    
#normalize mean power between 0-1
specm=(specm-np.min(specm))/np.ptp(specm)

#create chromagram of pitches X time points
chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=frame_length)

#sort pitches by overall power 
chromasort=np.argsort(np.mean(chroma,axis=1))[::-1]



########################################
########################################
########################################
########################################
########################################


if args.classes:
    classes=args.classes
    if len(classes) not in [12,num_classes]:
        raise ValueError("The number of classes entered in the --class argument must equal 12 or [num_classes] if specified")
    
elif args.use_previous_classes==1:
    cvs=np.load('class_vectors.npy')
    classes=list(np.where(cvs[0]>0)[0])
    
else: #select 12 random classes
    cls1000=list(range(1000))
    random.shuffle(cls1000)
    classes=cls1000[:12]
    



if sort_classes_by_power==1:

    classes=[classes[s] for s in np.argsort(chromasort[:num_classes])]



#initialize first class vector
cv1=np.zeros(1000)
for pi,p in enumerate(chromasort[:num_classes]):
    
    if num_classes < 12:
        cv1[classes[pi]] = chroma[p][np.min([np.where(chrow>0)[0][0] for chrow in chroma])]       
    else:
        cv1[classes[p]] = chroma[p][np.min([np.where(chrow>0)[0][0] for chrow in chroma])]

#initialize first noise vector
nv1 = truncated_noise_sample(truncation=truncation)[0]

#initialize list of class and noise vectors
class_vectors=[cv1]
noise_vectors=[nv1]

#initialize previous vectors (will be used to track the previous frame)
cvlast=cv1
nvlast=nv1


#initialize the direction of noise vector unit updates
update_dir=np.zeros(128)
for ni,n in enumerate(nv1):
    if n<0:
        update_dir[ni] = 1
    else:
        update_dir[ni] = -1


#initialize noise unit update
update_last=np.zeros(128)


########################################
########################################
########################################
########################################
########################################


#get new jitters
def new_jitters(jitter):
    jitters=np.zeros(128)
    for j in range(128):
        if random.uniform(0,1)<0.5:
            jitters[j]=1
        else:
            jitters[j]=1-jitter        
    return jitters


#get new update directions
def new_update_dir(nv2,update_dir):
    for ni,n in enumerate(nv2):                  
        if n >= 2*truncation - tempo_sensitivity:
            update_dir[ni] = -1  
                        
        elif n < -2*truncation + tempo_sensitivity:
            update_dir[ni] = 1   
    return update_dir


#smooth class vectors
def smooth(class_vectors,smooth_factor):
    
    if smooth_factor==1:
        return class_vectors
    
    class_vectors_terp=[]
    for c in range(int(np.floor(len(class_vectors)/smooth_factor)-1)):  
        ci=c*smooth_factor          
        cva=np.mean(class_vectors[int(ci):int(ci)+smooth_factor],axis=0)
        cvb=np.mean(class_vectors[int(ci)+smooth_factor:int(ci)+smooth_factor*2],axis=0)
                    
        for j in range(smooth_factor):                                 
            cvc = cva*(1-j/(smooth_factor-1)) + cvb*(j/(smooth_factor-1))                                          
            class_vectors_terp.append(cvc)
            
    return np.array(class_vectors_terp)


#normalize class vector between 0-1
def normalize_cv(cv2):
    min_class_val = min(i for i in cv2 if i != 0)
    for ci,c in enumerate(cv2):
        if c==0:
            cv2[ci]=min_class_val    
    cv2=(cv2-min_class_val)/np.ptp(cv2) 
    
    return cv2


print('\nGenerating input vectors \n')

for i in tqdm(range(len(gradm))):   
    
    #print progress
    pass

    #update jitter vector every 100 frames by setting ~half of noise vector units to lower sensitivity
    if i%200==0:
        jitters=new_jitters(jitter)

    #get last noise vector
    nv1=nvlast

    #set noise vector update based on direction, sensitivity, jitter, and combination of overall power and gradient of power
    update = np.array([tempo_sensitivity for k in range(128)]) * (gradm[i]+specm[i]) * update_dir * jitters 
    
    #smooth the update with the previous update (to avoid overly sharp frame transitions)
    update=(update+update_last*3)/4
    
    #set last update
    update_last=update
        
    #update noise vector
    nv2=nv1+update

    #append to noise vectors
    noise_vectors.append(nv2)
    
    #set last noise vector
    nvlast=nv2
                   
    #update the direction of noise units
    update_dir=new_update_dir(nv2,update_dir)

    #get last class vector
    cv1=cvlast
    
    #generate new class vector
    cv2=np.zeros(1000)
    for j in range(num_classes):
        
        cv2[classes[j]] = (cvlast[classes[j]] + ((chroma[chromasort[j]][i])/(pitch_sensitivity)))/(1+(1/((pitch_sensitivity))))

    #if more than 6 classes, normalize new class vector between 0 and 1, else simply set max class val to 1
    if num_classes > 6:
        cv2=normalize_cv(cv2)
    else:
        cv2=cv2/np.max(cv2)
    
    #adjust depth    
    cv2=cv2*depth
    
    #this prevents rare bugs where all classes are the same value
    if np.std(cv2[np.where(cv2!=0)]) < 0.0000001:
        cv2[classes[0]]=cv2[classes[0]]+0.01

    #append new class vector
    class_vectors.append(cv2)
    
    #set last class vector
    cvlast=cv2


#interpolate between class vectors of bin size [smooth_factor] to smooth frames 
class_vectors=smooth(class_vectors,smooth_factor)


#check whether to use vectors from last run
if use_previous_vectors==1:   
    #load vectors from previous run
    class_vectors=np.load('class_vectors.npy')
    noise_vectors=np.load('noise_vectors.npy')
else:
    #save record of vectors for current video
    np.save('class_vectors.npy',class_vectors)
    np.save('noise_vectors.npy',noise_vectors)



########################################
########################################
########################################
########################################
########################################
    

#convert to Tensor
noise_vectors = torch.Tensor(np.array(noise_vectors))      
class_vectors = torch.Tensor(np.array(class_vectors))      


#Generate frames in batches of batch_size

print('\n\nGenerating frames \n')

#send to CUDA if running on GPU
model=model.to(device)
noise_vectors=noise_vectors.to(device)
class_vectors=class_vectors.to(device)


frames = []

for i in tqdm(range(frame_lim)):
    
    #print progress
    pass

    if (i+1)*batch_size > len(class_vectors):
        torch.cuda.empty_cache()
        break
    
    #get batch
    noise_vector=noise_vectors[i*batch_size:(i+1)*batch_size]
    class_vector=class_vectors[i*batch_size:(i+1)*batch_size]

    # Generate images
    with torch.no_grad():
        output = model(noise_vector, class_vector, truncation)

    output_cpu=output.cpu().data.numpy()

    #convert to image array and add to frames
    for out in output_cpu:    
        im=np.array(toimage(out))
        frames.append(im)
        
    #empty cuda cache
    torch.cuda.empty_cache()



#Save video  
aud = mpy.AudioFileClip(song, fps = 44100) 

if args.duration:
    aud.duration=args.duration

clip = mpy.ImageSequenceClip(frames, fps=22050/frame_length)
clip = clip.set_audio(aud)
clip.write_videofile(outname,audio_codec='aac')





