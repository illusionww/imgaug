from __future__ import print_function, division, absolute_import
import random
import numpy as np
import copy
import numbers
import cv2
import math
from scipy import misc, ndimage
import multiprocessing
import threading
import traceback
import sys
import six
import six.moves as sm
import os
import skimage.draw
import skimage.measure
import collections
import time

if sys.version_info[0] == 2:
    import cPickle as pickle
    from Queue import Empty as QueueEmpty, Full as QueueFull
elif sys.version_info[0] == 3:
    import pickle
    from queue import Empty as QueueEmpty, Full as QueueFull
    xrange = range

ALL = "ALL"

# filepath to the quokka image
QUOKKA_FP = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "quokka.jpg"
)

DEFAULT_FONT_FP = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "DejaVuSans.ttf"
)

# We instantiate a current/global random state here once.
# One can also call np.random, but that is (in contrast to np.random.RandomState)
# a module and hence cannot be copied via deepcopy. That's why we use RandomState
# here (and in all augmenters) instead of np.random.
CURRENT_RANDOM_STATE = np.random.RandomState(42)

def is_np_array(val):
    """
    Checks whether a variable is a numpy array.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is a numpy array. Otherwise False.

    """
    # using np.generic here seems to also fire for scalar numpy values even
    # though those are not arrays
    #return isinstance(val, (np.ndarray, np.generic))
    return isinstance(val, np.ndarray)

def is_single_integer(val):
    """
    Checks whether a variable is an integer.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is an integer. Otherwise False.

    """
    return isinstance(val, numbers.Integral) and not isinstance(val, bool)

def is_single_float(val):
    """
    Checks whether a variable is a float.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is a float. Otherwise False.

    """
    return isinstance(val, numbers.Real) and not is_single_integer(val) and not isinstance(val, bool)

def is_single_number(val):
    """
    Checks whether a variable is a number, i.e. an integer or float.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is a number. Otherwise False.

    """
    return is_single_integer(val) or is_single_float(val)

def is_iterable(val):
    """
    Checks whether a variable is iterable.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is an iterable. Otherwise False.

    """
    return isinstance(val, collections.Iterable)

# TODO convert to is_single_string() or rename is_single_integer/float/number()
def is_string(val):
    """
    Checks whether a variable is a string.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is a string. Otherwise False.

    """
    return isinstance(val, six.string_types)

def is_integer_array(val):
    """
    Checks whether a variable is a numpy integer array.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is a numpy integer array. Otherwise False.

    """
    return is_np_array(val) and issubclass(val.dtype.type, np.integer)

def is_float_array(val):
    """
    Checks whether a variable is a numpy float array.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is a numpy float array. Otherwise False.

    """
    return is_np_array(val) and issubclass(val.dtype.type, np.floating)

def is_callable(val):
    """
    Checks whether a variable is a callable, e.g. a function.

    Parameters
    ----------
    val : anything
        The variable to
        check.

    Returns
    -------
    out : bool
        True if the variable is a callable. Otherwise False.

    """
    # python 3.x with x <= 2 does not support callable(), apparently
    if sys.version_info[0] == 3 and sys.version_info[1] <= 2:
        return hasattr(val, '__call__')
    else:
        return callable(val)

def caller_name():
    """
    Returns the name of the caller, e.g. a function.

    Returns
    -------
    name : str
        The name of the caller as a string

    """
    return sys._getframe(1).f_code.co_name

def seed(seedval):
    """
    Set the seed used by the global random state and thereby all randomness
    in the library.

    This random state is by default by all augmenters. Under special
    circumstances (e.g. when an augmenter is switched to deterministic mode),
    the global random state is replaced by another -- local -- one.
    The replacement is dependent on the global random state.

    Parameters
    ----------
    seedval : int
        The seed to
        use.
    """
    CURRENT_RANDOM_STATE.seed(seedval)

def current_random_state():
    """
    Returns the current/global random state of the library.

    Returns
    ----------
    out : np.random.RandomState
        The current/global random state.

    """
    return CURRENT_RANDOM_STATE

def new_random_state(seed=None, fully_random=False):
    """
    Returns a new random state.

    Parameters
    ----------
    seed : None or int, optional(default=None)
        Optional seed value to use.
        The same datatypes are allowed as for np.random.RandomState(seed).

    fully_random : bool, optional(default=False)
        Whether to use numpy's random initialization for the
        RandomState (used if set to True). If False, a seed is sampled from
        the global random state, which is a bit faster and hence the default.

    Returns
    -------
    out : np.random.RandomState
        The new random state.

    """
    if seed is None:
        if not fully_random:
            # sample manually a seed instead of just RandomState(),
            # because the latter one
            # is way slower.
            seed = CURRENT_RANDOM_STATE.randint(0, 10**6, 1)[0]
    return np.random.RandomState(seed)

def dummy_random_state():
    """
    Returns a dummy random state that is always based on a seed of 1.

    Returns
    -------
    out : np.random.RandomState
        The new random state.

    """
    return np.random.RandomState(1)

def copy_random_state(random_state, force_copy=False):
    """
    Creates a copy of a random state.

    Parameters
    ----------
    random_state : np.random.RandomState
        The random state to
        copy.

    force_copy : bool, optional(default=False)
        If True, this function will always create a copy of every random
        state. If False, it will not copy numpy's default random state,
        but all other random states.

    Returns
    -------
    rs_copy : np.random.RandomState
        The copied random state.

    """
    if random_state == np.random and not force_copy:
        return random_state
    else:
        rs_copy = dummy_random_state()
        orig_state = random_state.get_state()
        rs_copy.set_state(orig_state)
        return rs_copy

def derive_random_state(random_state):
    """
    Create a new random states based on an existing random state or seed.

    Parameters
    ----------
    random_state : np.random.RandomState
        Random state or seed from which to derive the new random state.

    Returns
    -------
    result : np.random.RandomState
        Derived random state.

    """
    return derive_random_states(random_state, n=1)[0]

# TODO use this everywhere instead of manual seed + create
def derive_random_states(random_state, n=1):
    """
    Create N new random states based on an existing random state or seed.

    Parameters
    ----------
    random_state : np.random.RandomState
        Random state or seed from which to derive new random states.

    n : int, optional(default=1)
        Number of random states to derive.

    Returns
    -------
    result : list of np.random.RandomState
        Derived random states.

    """
    seed = random_state.randint(0, 10**6, 1)[0]
    return [new_random_state(seed+i) for i in sm.xrange(n)]

def forward_random_state(random_state):
    """
    Forward the internal state of a random state.

    This makes sure that future calls to the random_state will produce new random values.

    Parameters
    ----------
    random_state : np.random.RandomState
        Random state to forward.

    """
    random_state.uniform()

# TODO
# def from_json(json_str):
#    pass

def quokka(size=None):
    """
    Returns an image of a quokka as a numpy array.

    Parameters
    ----------
    size : None or float or tuple of two ints, optional(default=None)
        Size of the output image. Input into scipy.misc.imresize.
        Usually expected to be a tuple (H, W), where H is the desired height
        and W is the width. If None, then the image will not be resized.

    Returns
    -------
    img : (H,W,3) ndarray
        The image array of dtype uint8.

    """
    img = ndimage.imread(QUOKKA_FP, mode="RGB")
    if size is not None:
        img = misc.imresize(img, size)
    return img

def quokka_square(size=None):
    """
    Returns an (square) image of a quokka as a numpy array.

    Parameters
    ----------
    size : None or float or tuple of two ints, optional(default=None)
        Size of the output image. Input into scipy.misc.imresize.
        Usually expected to be a tuple (H, W), where H is the desired height
        and W is the width. If None, then the image will not be resized.

    Returns
    -------
    img : (H,W,3) ndarray
        The image array of dtype uint8.

    """
    img = ndimage.imread(QUOKKA_FP, mode="RGB")
    img = img[0:643, 0:643]
    if size is not None:
        img = misc.imresize(img, size)
    return img

def angle_between_vectors(v1, v2):
    """
    Returns the angle in radians between vectors 'v1' and 'v2'.

    From http://stackoverflow.com/questions/2827393/angles-between-two-n-dimensional-vectors-in-python

    Parameters
    ----------
    {v1, v2} : (N,) ndarray
        Input
        vectors.

    Returns
    -------
    out : float
        Angle in radians.

    Examples
    --------
    >>> angle_between((1, 0, 0), (0, 1, 0))
    1.5707963267948966

    >>> angle_between((1, 0, 0), (1, 0, 0))
    0.0

    >>> angle_between((1, 0, 0), (-1, 0, 0))
    3.141592653589793

    """
    v1_u = v1 / np.linalg.norm(v1)
    v2_u = v2 / np.linalg.norm(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))

def draw_text(img, y, x, text, color=[0, 255, 0], size=25): # pylint: disable=locally-disabled, dangerous-default-value, line-too-long
    """
    Draw text on an image.

    This uses by default DejaVuSans as its font, which is included in the
    library.

    Parameters
    ----------
    img : (H,W,3) ndarray
        The image array to draw text on.
        Expected to be of dtype uint8 or float32 (value range 0.0 to 255.0).

    {y, x} : int
        x- and y- coordinate of the top left corner of the
        text.

    color : iterable of 3 ints, optional(default=[0, 255, 0])
        Color of the text to draw. For RGB-images this is expected to be
        an RGB color.

    size : int, optional(default=25)
        Font size of the text to
        draw.

    Returns
    -------
    img_np : (H,W,3) ndarray
        Input image with text drawn on it.

    """
    # keeping PIL here so that it is not a dependency of the library right now
    from PIL import Image, ImageDraw, ImageFont

    do_assert(img.dtype in [np.uint8, np.float32])

    input_dtype = img.dtype
    if img.dtype == np.float32:
        img = img.astype(np.uint8)

    for i in range(len(color)):
        val = color[i]
        if isinstance(val, float):
            val = int(val * 255)
            val = np.clip(val, 0, 255)
            color[i] = val

    img = Image.fromarray(img)
    font = ImageFont.truetype(DEFAULT_FONT_FP, size)
    context = ImageDraw.Draw(img)
    context.text((x, y), text, fill=tuple(color), font=font)
    img_np = np.asarray(img)
    img_np.setflags(write=True)  # PIL/asarray returns read only array

    if img_np.dtype != input_dtype:
        img_np = img_np.astype(input_dtype)

    return img_np


# TODO rename sizes to size?
def imresize_many_images(images, sizes=None, interpolation=None):
    """
    Resize many images to a specified size.

    Parameters
    ----------
    images : (N,H,W,C) ndarray
        Array of the images to resize.
        Expected to usually be of dtype uint8.

    sizes : float or iterable of two ints or iterable of two floats
        The new size of the images, given either as a fraction (a single float) or as
        a (height, width) tuple of two integers or as a (height fraction, width fraction)
        tuple of two floats.

    interpolation : None or string or int, optional(default=None)
        The interpolation to use during resize.
        If int, then expected to be one of:

            * cv2.INTER_NEAREST (nearest neighbour interpolation)
            * cv2.INTER_LINEAR (linear interpolation)
            * cv2.INTER_AREA (area interpolation)
            * cv2.INTER_CUBIC (cubic interpolation)

        If string, then expected to be one of:

            * "nearest" (identical to cv2.INTER_NEAREST)
            * "linear" (identical to cv2.INTER_LINEAR)
            * "area" (identical to cv2.INTER_AREA)
            * "cubic" (identical to cv2.INTER_CUBIC)

        If None, the interpolation will be chosen automatically. For size
        increases, area interpolation will be picked and for size decreases,
        linear interpolation will be picked.

    Returns
    -------
    result : (N,H',W',C) ndarray
        Array of the resized images.

    Examples
    --------
    >>> imresize_many_images(np.zeros((2, 16, 16, 3), dtype=np.uint8), 2.0)
    Converts 2 RGB images of height and width 16 to images of height and width 16*2 = 32.

    >>> imresize_many_images(np.zeros((2, 16, 16, 3), dtype=np.uint8), (16, 32))
    Converts 2 RGB images of height and width 16 to images of height 16 and width 32.

    >>> imresize_many_images(np.zeros((2, 16, 16, 3), dtype=np.uint8), (2.0, 4.0))
    Converts 2 RGB images of height and width 16 to images of height 32 and width 64.

    """
    shape = images.shape
    do_assert(images.ndim == 4, "Expected array of shape (N, H, W, C), got shape %s" % (str(shape),))
    nb_images = shape[0]
    im_height, im_width = shape[1], shape[2]
    nb_channels = shape[3]
    if is_single_float(sizes):
        do_assert(sizes > 0.0)
        height = int(round(im_height * sizes))
        width = int(round(im_width * sizes))
    else:
        do_assert(len(sizes) == 2)
        all_int = all([is_single_integer(size) for size in sizes])
        all_float = all([is_single_float(size) for size in sizes])
        do_assert(all_int or all_float)
        if all_int:
            height, width = sizes[0], sizes[1]
        else:
            height = int(round(im_height * sizes[0]))
            width = int(round(im_width * sizes[1]))

    if height == im_height and width == im_width:
        return np.copy(images)

    ip = interpolation
    do_assert(ip is None or ip in ["nearest", "linear", "area", "cubic", cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_AREA, cv2.INTER_CUBIC])
    if ip is None:
        if height > im_height or width > im_width:
            ip = cv2.INTER_AREA
        else:
            ip = cv2.INTER_LINEAR
    elif ip in ["nearest", cv2.INTER_NEAREST]:
        ip = cv2.INTER_NEAREST
    elif ip in ["linear", cv2.INTER_LINEAR]:
        ip = cv2.INTER_LINEAR
    elif ip in ["area", cv2.INTER_AREA]:
        ip = cv2.INTER_AREA
    else:  # if ip in ["cubic", cv2.INTER_CUBIC]:
        ip = cv2.INTER_CUBIC

    result = np.zeros((nb_images, height, width, nb_channels), dtype=images.dtype)
    for img_idx in sm.xrange(nb_images):
        # TODO fallback to scipy here if image isn't uint8
        result_img = cv2.resize(images[img_idx], (width, height), interpolation=ip)
        if len(result_img.shape) == 2:
            result_img = result_img[:, :, np.newaxis]
        result[img_idx] = result_img.astype(images.dtype)
    return result


def imresize_single_image(image, sizes, interpolation=None):
    """
    Resizes a single image.

    Parameters
    ----------
    image : (H,W,C) ndarray or (H,W) ndarray
        Array of the image to resize.
        Expected to usually be of dtype uint8.

    sizes : float or iterable of two ints or iterable of two floats
        See `imresize_many_images()`.

    interpolation : None or string or int, optional(default=None)
        See `imresize_many_images()`.

    Returns
    -------
    out : (H',W',C) ndarray or (H',W') ndarray
        The resized image.

    """
    grayscale = False
    if image.ndim == 2:
        grayscale = True
        image = image[:, :, np.newaxis]
    do_assert(len(image.shape) == 3, image.shape)
    rs = imresize_many_images(image[np.newaxis, :, :, :], sizes, interpolation=interpolation)
    if grayscale:
        return np.squeeze(rs[0, :, :, 0])
    else:
        return rs[0, ...]


def pad(arr, top=0, right=0, bottom=0, left=0, mode="constant", cval=0):
    """
    Pad an image-like array on its top/right/bottom/left side.

    This function is a wrapper around `numpy.pad()`.

    Parameters
    ----------
    arr : (H,W) or (H,W,C) ndarray
        Image-like array to pad.

    top : int, optional(default=0)
        Amount of pixels to add at the top side of the image. Must be 0 or greater.

    right : int, optional(default=0)
        Amount of pixels to add at the right side of the image. Must be 0 or greater.

    bottom : int, optional(default=0)
        Amount of pixels to add at the bottom side of the image. Must be 0 or greater.

    left : int, optional(default=0)
        Amount of pixels to add at the left side of the image. Must be 0 or greater.

    mode : string, optional(default="constant")
        Padding mode to use. See `numpy.pad()` for details.

    cval : number, optional(default=0)
        Value to use for padding if mode="constant". See `numpy.pad()` for details.

    Returns
    -------
    arr_pad : (H',W') or (H',W',C) ndarray
        Padded array with height H'=H+top+bottom and width W'=W+left+right.

    """
    assert arr.ndim in [2, 3]
    assert top >= 0
    assert right >= 0
    assert bottom >= 0
    assert left >= 0
    if top > 0 or right > 0 or bottom > 0 or left > 0:
        paddings_np = [(top, bottom), (left, right)]  # paddings for 2d case
        if arr.ndim == 3:
            paddings_np.append((0, 0))  # add paddings for 3d case

        if mode == "constant":
            arr_pad = np.pad(
                arr,
                paddings_np,
                mode=mode,
                constant_values=cval
            )
        else:
            arr_pad = np.pad(
                arr,
                paddings_np,
                mode=mode
            )
        return arr_pad
    else:
        return np.copy(arr)


def compute_paddings_for_aspect_ratio(arr, aspect_ratio):
    """
    Compute the amount of pixels by which an array has to be padded to fulfill an aspect ratio.

    The aspect ratio is given as width/height.
    Depending on which dimension is smaller (height or width), only the corresponding
    sides (left/right or top/bottom) will be padded. In each case, both of the sides will
    be padded equally.

    Parameters
    ----------
    arr : (H,W) or (H,W,C) ndarray
        Image-like array for which to compute pad amounts.

    aspect_ratio : float
        Target aspect ratio, given as width/height. E.g. 2.0 denotes the image having twice
        as much width as height.

    Returns
    -------
    result : tuple of ints
        Required paddign amounts to reach the target aspect ratio, given as a tuple
        of the form (top, right, bottom, left).

    """
    assert arr.ndim in [2, 3]
    assert aspect_ratio > 0
    height, width = arr.shape[0:2]
    assert height > 0
    aspect_ratio_current = width / height

    pad_top = 0
    pad_right = 0
    pad_bottom = 0
    pad_left = 0

    if aspect_ratio_current < aspect_ratio:
        # vertical image, height > width
        diff = (aspect_ratio * height) - width
        pad_right = int(np.ceil(diff / 2))
        pad_left = int(np.floor(diff / 2))
    elif aspect_ratio_current > aspect_ratio:
        # horizontal image, width > height
        diff = ((1/aspect_ratio) * width) - height
        pad_top = int(np.ceil(diff / 2))
        pad_bottom = int(np.floor(diff / 2))

    return (pad_top, pad_right, pad_bottom, pad_left)


def pad_to_aspect_ratio(arr, aspect_ratio, mode="constant", cval=0, return_pad_amounts=False):
    """
    Pad an image-like array on its sides so that it matches a target aspect ratio.

    Depending on which dimension is smaller (height or width), only the corresponding
    sides (left/right or top/bottom) will be padded. In each case, both of the sides will
    be padded equally.

    Parameters
    ----------
    arr : (H,W) or (H,W,C) ndarray
        Image-like array to pad.

    aspect_ratio : float
        Target aspect ratio, given as width/height. E.g. 2.0 denotes the image having twice
        as much width as height.

    mode : string, optional(default="constant")
        Padding mode to use. See `numpy.pad()` for details.

    cval : number, optional(default=0)
        Value to use for padding if mode="constant". See `numpy.pad()` for details.

    return_pad_amounts : bool, optional(default=False)
        If False, then only the padded image will be returned. If True, a tuple with two
        entries will be returned, where the first entry is the padded image and the second
        entry are the amounts by which each image side was padded. These amounts are again a
        tuple of the form (top, right, bottom, left), with each value being an integer.

    Returns
    -------
    result : tuple
        First tuple entry: Padded image as (H',W') or (H',W',C) ndarray, fulfulling the given
        aspect_ratio.
        Second tuple entry: Amounts by which the image was padded on each side, given
        as a tuple (top, right, bottom, left).
        If return_pad_amounts is False, then only the image is returned.

    """
    pad_top, pad_right, pad_bottom, pad_left = compute_paddings_for_aspect_ratio(arr, aspect_ratio)
    arr_padded = pad(
        arr,
        top=pad_top,
        right=pad_right,
        bottom=pad_bottom,
        left=pad_left,
        mode=mode,
        cval=cval
    )

    if return_pad_amounts:
        return arr_padded, (pad_top, pad_right, pad_bottom, pad_left)
    else:
        return arr_padded


def pool(arr, block_size, func, cval=0, preserve_dtype=True):
    """
    Rescale an array by pooling values within blocks.

    Parameters
    ----------
    arr : (H,W) or (H,W,C) ndarray
        Image-like array to pool. Ideally of datatype np.float64.

    block_size : int or tuple of two ints or tuple of three ints
        Spatial size of each group of each values to pool, aka kernel size.
        If a single integer, then a symmetric block of that size along height and width will
        be used.
        If a tuple of two values, it is assumed to be the block size along height and width
        of the image-like, with pooling happening per channel.
        If a tuple of three values, it is assuemd to be the block size along height, width and
        channels.

    func : callable
        Function to apply to a given block in order to convert it to a single number,
        e.g. np.average, np.min, np.max.

    cval : number, optional(default=0)
        Value to use in order to pad the array along its border if the array cannot be divided
        by block_size without remainder.

    preserve_dtype : bool, optional(default=True)
        Whether to convert the array back to the input datatype if it is changed away from
        that in the pooling process.

    Returns
    -------
    arr_reduced : (H',W') or (H',W',C') ndarray
        Array after pooling.

    """
    assert arr.ndim in [2, 3]
    is_valid_int = is_single_integer(block_size) and block_size >= 1
    is_valid_tuple = is_iterable(block_size) and len(block_size) in [2, 3] and [is_single_integer(val) and val >= 1 for val in block_size]
    assert is_valid_int or is_valid_tuple

    if is_single_integer(block_size):
        block_size = [block_size, block_size]
    if len(block_size) < arr.ndim:
        block_size = list(block_size) + [1]

    input_dtype = arr.dtype
    arr_reduced = skimage.measure.block_reduce(arr, tuple(block_size), func, cval=cval)
    if preserve_dtype and arr_reduced.dtype.type != input_dtype:
        arr_reduced = arr_reduced.astype(input_dtype)
    return arr_reduced


def avg_pool(arr, block_size, cval=0, preserve_dtype=True):
    """
    Rescale an array using average pooling.

    Parameters
    ----------
    arr : (H,W) or (H,W,C) ndarray
        Image-like array to pool. See `pool()` for details.

    block_size : int or tuple of two ints or tuple of three ints
        Size of each block of values to pool. See `pool()` for details.

    cval : number, optional(default=0)
        Padding value. See `pool()` for details.

    preserve_dtype : bool, optional(default=True)
        Whether to preserve the input array dtype. See `pool()` for details.

    Returns
    -------
    arr_reduced : (H',W') or (H',W',C') ndarray
        Array after average pooling.

    """
    return pool(arr, block_size, np.average, cval=cval, preserve_dtype=preserve_dtype)


def max_pool(arr, block_size, cval=0, preserve_dtype=True):
    """
    Rescale an array using max-pooling.

    Parameters
    ----------
    arr : (H,W) or (H,W,C) ndarray
        Image-like array to pool. See `pool()` for details.

    block_size : int or tuple of two ints or tuple of three ints
        Size of each block of values to pool. See `pool()` for details.

    cval : number, optional(default=0)
        Padding value. See `pool()` for details.

    preserve_dtype : bool, optional(default=True)
        Whether to preserve the input array dtype. See `pool()` for details.

    Returns
    -------
    arr_reduced : (H',W') or (H',W',C') ndarray
        Array after max-pooling.

    """
    return pool(arr, block_size, np.max, cval=cval, preserve_dtype=preserve_dtype)


def draw_grid(images, rows=None, cols=None):
    """
    Converts multiple input images into a single image showing them in a grid.

    Parameters
    ----------
    images : (N,H,W,3) ndarray or iterable of (H,W,3) array
        The input images to convert to a grid.
        Expected to be RGB and have dtype uint8.

    rows : None or int, optional(default=None)
        The number of rows to show in the grid.
        If None, it will be automatically derived.

    cols : None or int, optional(default=None)
        The number of cols to show in the grid.
        If None, it will be automatically derived.

    Returns
    -------
    grid : (H',W',3) ndarray
        Image of the generated grid.

    """
    if is_np_array(images):
        do_assert(images.ndim == 4)
    else:
        do_assert(is_iterable(images) and is_np_array(images[0]) and images[0].ndim == 3)

    nb_images = len(images)
    do_assert(nb_images > 0)
    cell_height = max([image.shape[0] for image in images])
    cell_width = max([image.shape[1] for image in images])
    channels = set([image.shape[2] for image in images])
    do_assert(len(channels) == 1, "All images are expected to have the same number of channels, but got channel set %s with length %d instead." % (str(channels), len(channels)))
    nb_channels = list(channels)[0]
    if rows is None and cols is None:
        rows = cols = int(math.ceil(math.sqrt(nb_images)))
    elif rows is not None:
        cols = int(math.ceil(nb_images / rows))
    elif cols is not None:
        rows = int(math.ceil(nb_images / cols))
    do_assert(rows * cols >= nb_images)

    width = cell_width * cols
    height = cell_height * rows
    grid = np.zeros((height, width, nb_channels), dtype=np.uint8)
    cell_idx = 0
    for row_idx in sm.xrange(rows):
        for col_idx in sm.xrange(cols):
            if cell_idx < nb_images:
                image = images[cell_idx]
                cell_y1 = cell_height * row_idx
                cell_y2 = cell_y1 + image.shape[0]
                cell_x1 = cell_width * col_idx
                cell_x2 = cell_x1 + image.shape[1]
                grid[cell_y1:cell_y2, cell_x1:cell_x2, :] = image
            cell_idx += 1

    return grid

def show_grid(images, rows=None, cols=None):
    """
    Converts the input images to a grid image and shows it in a new window.

    This function wraps around scipy.misc.imshow(), which requires the
    `see <image>` command to work. On Windows systems, this tends to not be
    the case.

    Parameters
    ----------
    images : (N,H,W,3) ndarray or iterable of (H,W,3) array
        See `draw_grid()`.

    rows : None or int, optional(default=None)
        See `draw_grid()`.

    cols : None or int, optional(default=None)
        See `draw_grid()`.

    """
    grid = draw_grid(images, rows=rows, cols=cols)
    misc.imshow(grid)

def do_assert(condition, message="Assertion failed."):
    """
    Function that behaves equally to an `assert` statement, but raises an
    Exception.

    This is added because `assert` statements are removed in optimized code.
    It replaces `assert` statements throughout the library that should be
    kept even in optimized code.

    Parameters
    ----------
    condition : bool
        If False, an exception is raised.

    message : string, optional(default="Assertion failed.")
        Error message.

    """
    if not condition:
        raise AssertionError(str(message))

class HooksImages(object):
    """
    Class to intervene with image augmentation runs.

    This is e.g. useful to dynamically deactivate some augmenters.

    Parameters
    ----------
    activator : None or callable, optional(default=None)
        A function that gives permission to execute an augmenter.
        The expected interface is `f(images, augmenter, parents, default)`,
        where `images` are the input images to augment, `augmenter` is the
        instance of the augmenter to execute, `parents` are previously
        executed augmenters and `default` is an expected default value to be
        returned if the activator function does not plan to make a decision
        for the given inputs.

    propagator : None or callable, optional(default=None)
        A function that gives permission to propagate the augmentation further
        to the children of an augmenter. This happens after the activator.
        In theory, an augmenter may augment images itself (if allowed by the
        activator) and then execute child augmenters afterwards (if allowed by
        the propagator). If the activator returned False, the propagation step
        will never be executed.
        The expected interface is `f(images, augmenter, parents, default)`,
        with all arguments having identical meaning to the activator.

    preprocessor : None or callable, optional(default=None)
        A function to call before an augmenter performed any augmentations.
        The interface is `f(images, augmenter, parents)`,
        with all arguments having identical meaning to the activator.
        It is expected to return the input images, optionally modified.

    postprocessor : None or callable, optional(default=None)
        A function to call after an augmenter performed augmentations.
        The interface is the same as for the preprocessor.

    Examples
    --------
    >>> seq = iaa.Sequential([
    >>>     iaa.GaussianBlur(3.0, name="blur"),
    >>>     iaa.Dropout(0.05, name="dropout"),
    >>>     iaa.Affine(translate_px=-5, name="affine")
    >>> ])
    >>>
    >>> def activator(images, augmenter, parents, default):
    >>>     return False if augmenter.name in ["blur", "dropout"] else default
    >>>
    >>> seq_det = seq.to_deterministic()
    >>> images_aug = seq_det.augment_images(images)
    >>> heatmaps_aug = seq_det.augment_images(
    >>>     heatmaps,
    >>>     hooks=ia.HooksImages(activator=activator)
    >>> )

    This augments images and their respective heatmaps in the same way.
    The heatmaps however are only modified by Affine, not by GaussianBlur or
    Dropout.

    """

    #def __init__(self, activator=None, propagator=None, preprocessor=None, postprocessor=None, propagation_method=None):
    def __init__(self, activator=None, propagator=None, preprocessor=None, postprocessor=None):
        self.activator = activator
        self.propagator = propagator
        self.preprocessor = preprocessor
        self.postprocessor = postprocessor
        #self.propagation_method = propagation_method

    def is_activated(self, images, augmenter, parents, default):
        """
        Returns whether an augmenter may be executed.

        Returns
        -------
        out : bool
            If True, the augmenter may be executed. If False, it may
            not be executed.

        """
        if self.activator is None:
            return default
        else:
            return self.activator(images, augmenter, parents, default)

    # TODO is a propagating hook necessary? seems to be covered by activated
    # hook already
    def is_propagating(self, images, augmenter, parents, default):
        """
        Returns whether an augmenter may call its children to augment an
        image. This is independent of the augmenter itself possible changing
        the image, without calling its children. (Most (all?) augmenters with
        children currently dont perform any changes themselves.)

        Returns
        -------
        out : bool
            If True, the augmenter may be propagate to its children.
            If False, it may not.

        """
        if self.propagator is None:
            return default
        else:
            return self.propagator(images, augmenter, parents, default)

    #def get_propagation_method(self, images, augmenter, parents, child, default):
    #    if self.propagation_method is None:
    #        return default
    #    else:
    #        return self.propagation_method(images, augmenter, parents, child, default)

    def preprocess(self, images, augmenter, parents):
        """
        A function to be called before the augmentation of images starts (per
        augmenter).

        Returns
        -------
        out : (N,H,W,C) ndarray or (N,H,W) ndarray or list of (H,W,C) ndarray or list of (H,W) ndarray
            The input images, optionally modified.

        """
        if self.preprocessor is None:
            return images
        else:
            return self.preprocessor(images, augmenter, parents)

    def postprocess(self, images, augmenter, parents):
        """
        A function to be called after the augmentation of images was
        performed.

        Returns
        -------
        out : (N,H,W,C) ndarray or (N,H,W) ndarray or list of (H,W,C) ndarray or list of (H,W) ndarray
            The input images, optionally modified.

        """
        if self.postprocessor is None:
            return images
        else:
            return self.postprocessor(images, augmenter, parents)

class HooksHeatmaps(HooksImages):
    """
    Class to intervene with heatmap augmentation runs.

    This is e.g. useful to dynamically deactivate some augmenters.

    This class is currently the same as the one for images. This may or may
    not change in the future.

    """
    pass

class HooksKeypoints(HooksImages):
    """
    Class to intervene with keypoint augmentation runs.

    This is e.g. useful to dynamically deactivate some augmenters.

    This class is currently the same as the one for images. This may or may
    not change in the future.

    """
    pass


class Keypoint(object):
    """
    A single keypoint (aka landmark) on an image.

    Parameters
    ----------
    x : number
        Coordinate of the keypoint on the x axis.

    y : number
        Coordinate of the keypoint on the y axis.

    """

    def __init__(self, x, y):
        # these checks are currently removed because they are very slow for some
        # reason
        #assert is_single_integer(x), type(x)
        #assert is_single_integer(y), type(y)
        self.x = x
        self.y = y

    @property
    def x_int(self):
        """
        Return the keypoint's x-coordinate, rounded to the closest integer.

        Returns
        -------
        result : int
            Keypoint's x-coordinate, rounded to the closest integer.
        """
        return int(round(self.x))

    @property
    def y_int(self):
        """
        Return the keypoint's y-coordinate, rounded to the closest integer.

        Returns
        -------
        result : int
            Keypoint's y-coordinate, rounded to the closest integer.
        """
        return int(round(self.y))

    def project(self, from_shape, to_shape):
        """
        Project the keypoint onto a new position on a new image.

        E.g. if the keypoint is on its original image at x=(10 of 100 pixels)
        and y=(20 of 100 pixels) and is projected onto a new image with
        size (width=200, height=200), its new position will be (20, 40).

        This is intended for cases where the original image is resized.
        It cannot be used for more complex changes (e.g. padding, cropping).

        Parameters
        ----------
        from_shape : tuple
            Shape of the original image. (Before resize.)

        to_shape : tuple
            Shape of the new image. (After resize.)

        Returns
        -------
        out : Keypoint
            Keypoint object with new coordinates.

        """
        if from_shape[0:2] == to_shape[0:2]:
            return Keypoint(x=self.x, y=self.y)
        else:
            from_height, from_width = from_shape[0:2]
            to_height, to_width = to_shape[0:2]
            x = (self.x / from_width) * to_width
            y = (self.y / from_height) * to_height
            return Keypoint(x=x, y=y)

    def shift(self, x=0, y=0):
        """
        Move the keypoint around on an image.

        Parameters
        ----------
        x : number, optional(default=0)
            Move by this value on the x axis.

        y : number, optional(default=0)
            Move by this value on the y axis.

        Returns
        -------
        out : Keypoint
            Keypoint object with new coordinates.

        """
        return Keypoint(self.x + x, self.y + y)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Keypoint(x=%.8f, y=%.8f)" % (self.x, self.y)


class KeypointsOnImage(object):
    """
    Object that represents all keypoints on a single image.

    Parameters
    ----------
    keypoints : list of Keypoint
        List of keypoints on the image.

    shape : tuple of int
        The shape of the image on which the keypoints are placed.

    Examples
    --------
    >>> kps = [Keypoint(x=10, y=20), Keypoint(x=34, y=60)]
    >>> kps_oi = KeypointsOnImage(kps, shape=image.shape)

    """
    def __init__(self, keypoints, shape):
        #assert len(shape) == 3, "KeypointsOnImage requires shape tuples of form (H, W, C) but got %s. Use C=1 for 2-dimensional images." % (str(shape),)
        self.keypoints = keypoints
        if is_np_array(shape):
            self.shape = shape.shape
        else:
            do_assert(isinstance(shape, (tuple, list)))
            self.shape = tuple(shape)

    @property
    def height(self):
        return self.shape[0]

    @property
    def width(self):
        return self.shape[1]

    @property
    def empty(self):
        """
        Returns whether this object contains zero keypoints.

        Returns
        -------
        result : bool
            True if this object contains zero keypoints.
        """
        return len(self.keypoints) == 0

    def on(self, image):
        """
        Project keypoints from one image to a new one.

        Parameters
        ----------
        image : ndarray or tuple
            New image onto which the keypoints are to be projected.
            May also simply be that new image's shape tuple.

        Returns
        -------
        keypoints : KeypointsOnImage
            Object containing all projected keypoints.

        """
        if is_np_array(image):
            shape = image.shape
        else:
            shape = image

        if shape[0:2] == self.shape[0:2]:
            return self.deepcopy()
        else:
            keypoints = [kp.project(self.shape, shape) for kp in self.keypoints]
            return KeypointsOnImage(keypoints, shape)

    def draw_on_image(self, image, color=[0, 255, 0], size=3, copy=True, raise_if_out_of_image=False): # pylint: disable=locally-disabled, dangerous-default-value, line-too-long
        """
        Draw all keypoints onto a given image. Each keypoint is marked by a
        square of a chosen color and size.

        Parameters
        ----------
        image : (H,W,3) ndarray
            The image onto which to draw the keypoints.
            This image should usually have the same shape as
            set in KeypointsOnImage.shape.

        color : int or list of ints or tuple of ints or (3,) ndarray, optional(default=[0, 255, 0])
            The RGB color of all keypoints. If a single int `C`, then that is
            equivalent to (C,C,C).

        size : int, optional(default=3)
            The size of each point. If set to C, each square will have
            size CxC.

        copy : bool, optional(default=True)
            Whether to copy the image before drawing the points.

        raise_if_out_of_image : bool, optional(default=False)
            Whether to raise an exception if any keypoint is outside of the
            image.

        Returns
        -------
        image : (H,W,3) ndarray
            Image with drawn keypoints.

        """
        if copy:
            image = np.copy(image)

        height, width = image.shape[0:2]

        for keypoint in self.keypoints:
            y, x = keypoint.y_int, keypoint.x_int
            if 0 <= y < height and 0 <= x < width:
                x1 = max(x - size//2, 0)
                x2 = min(x + 1 + size//2, width)
                y1 = max(y - size//2, 0)
                y2 = min(y + 1 + size//2, height)
                image[y1:y2, x1:x2] = color
            else:
                if raise_if_out_of_image:
                    raise Exception("Cannot draw keypoint x=%.8f, y=%.8f on image with shape %s." % (y, x, image.shape))

        return image

    def shift(self, x=0, y=0):
        """
        Move the keypoints around on an image.

        Parameters
        ----------
        x : number, optional(default=0)
            Move each keypoint by this value on the x axis.

        y : number, optional(default=0)
            Move each keypoint by this value on the y axis.

        Returns
        -------
        out : KeypointsOnImage
            Keypoints after moving them.

        """
        keypoints = [keypoint.shift(x=x, y=y) for keypoint in self.keypoints]
        return KeypointsOnImage(keypoints, self.shape)

    def get_coords_array(self):
        """
        Convert the coordinates of all keypoints in this object to
        an array of shape (N,2).

        Returns
        -------
        result : (N, 2) ndarray
            Where N is the number of keypoints. Each first value is the
            x coordinate, each second value is the y coordinate.

        """
        result = np.zeros((len(self.keypoints), 2), np.float32)
        for i, keypoint in enumerate(self.keypoints):
            result[i, 0] = keypoint.x
            result[i, 1] = keypoint.y
        return result

    @staticmethod
    def from_coords_array(coords, shape):
        """
        Convert an array (N,2) with a given image shape to a KeypointsOnImage
        object.

        Parameters
        ----------
        coords : (N, 2) ndarray
            Coordinates of N keypoints on the original image.
            Each first entry (i, 0) is expected to be the x coordinate.
            Each second entry (i, 1) is expected to be the y coordinate.

        shape : tuple
            Shape tuple of the image on which the keypoints are placed.

        Returns
        -------
        out : KeypointsOnImage
            KeypointsOnImage object that contains all keypoints from the array.

        """
        keypoints = [Keypoint(x=coords[i, 0], y=coords[i, 1]) for i in sm.xrange(coords.shape[0])]
        return KeypointsOnImage(keypoints, shape)

    def to_keypoint_image(self, size=1):
        """
        Draws a new black image of shape (H,W,N) in which all keypoint coordinates
        are set to 255.
        (H=shape height, W=shape width, N=number of keypoints)

        This function can be used as a helper when augmenting keypoints with
        a method that only supports the augmentation of images.

        Parameters
        -------
        size : int
            Size of each (squared) point.

        Returns
        -------
        image : (H,W,N) ndarray
            Image in which the keypoints are marked. H is the height,
            defined in KeypointsOnImage.shape[0] (analogous W). N is the
            number of keypoints.
        """
        do_assert(len(self.keypoints) > 0)
        height, width = self.shape[0:2]
        image = np.zeros((height, width, len(self.keypoints)), dtype=np.uint8)
        do_assert(size % 2 != 0)
        sizeh = max(0, (size-1)//2)
        for i, keypoint in enumerate(self.keypoints):
            # TODO for float values spread activation over several cells
            # here and do voting at the end
            y = keypoint.y_int
            x = keypoint.x_int

            x1 = np.clip(x - sizeh, 0, width-1)
            x2 = np.clip(x + sizeh + 1, 0, width)
            y1 = np.clip(y - sizeh, 0, height-1)
            y2 = np.clip(y + sizeh + 1, 0, height)

            #if 0 <= y < height and 0 <= x < width:
            #    image[y, x, i] = 255
            if x1 < x2 and y1 < y2:
                image[y1:y2, x1:x2, i] = 128
            if 0 <= y < height and 0 <= x < width:
                image[y, x, i] = 255
        return image

    @staticmethod
    def from_keypoint_image(image, if_not_found_coords={"x": -1, "y": -1}, threshold=1, nb_channels=None): # pylint: disable=locally-disabled, dangerous-default-value, line-too-long
        """
        Converts an image generated by `to_keypoint_image()` back to
        an KeypointsOnImage object.

        Parameters
        ----------
        image : (H,W,N) ndarray
            The keypoints image. N is the number of
            keypoints.

        if_not_found_coords : tuple or list or dict or None
            Coordinates to use for keypoints that cannot be found in `image`.
            If this is a list/tuple, it must have two integer values. If it
            is a dictionary, it must have the keys "x" and "y". If this
            is None, then the keypoint will not be added to the final
            KeypointsOnImage object.

        threshold : int
            The search for keypoints works by searching for the argmax in
            each channel. This parameters contains the minimum value that
            the max must have in order to be viewed as a keypoint.

        nb_channels : None or int
            Number of channels of the image on which the keypoints are placed.
            Some keypoint augmenters require that information.
            If set to None, the keypoint's shape will be set
            to `(height, width)`, otherwise `(height, width, nb_channels)`.

        Returns
        -------
        out : KeypointsOnImage
            The extracted keypoints.

        """
        do_assert(len(image.shape) == 3)
        height, width, nb_keypoints = image.shape

        drop_if_not_found = False
        if if_not_found_coords is None:
            drop_if_not_found = True
            if_not_found_x = -1
            if_not_found_y = -1
        elif isinstance(if_not_found_coords, (tuple, list)):
            do_assert(len(if_not_found_coords) == 2)
            if_not_found_x = if_not_found_coords[0]
            if_not_found_y = if_not_found_coords[1]
        elif isinstance(if_not_found_coords, dict):
            if_not_found_x = if_not_found_coords["x"]
            if_not_found_y = if_not_found_coords["y"]
        else:
            raise Exception("Expected if_not_found_coords to be None or tuple or list or dict, got %s." % (type(if_not_found_coords),))

        keypoints = []
        for i in sm.xrange(nb_keypoints):
            maxidx_flat = np.argmax(image[..., i])
            maxidx_ndim = np.unravel_index(maxidx_flat, (height, width))
            found = (image[maxidx_ndim[0], maxidx_ndim[1], i] >= threshold)
            if found:
                keypoints.append(Keypoint(x=maxidx_ndim[1], y=maxidx_ndim[0]))
            else:
                if drop_if_not_found:
                    pass # dont add the keypoint to the result list, i.e. drop it
                else:
                    keypoints.append(Keypoint(x=if_not_found_x, y=if_not_found_y))

        out_shape = (height, width)
        if nb_channels is not None:
            out_shape += (nb_channels,)
        return KeypointsOnImage(keypoints, shape=out_shape)

    def copy(self):
        """
        Create a shallow copy of the KeypointsOnImage object.

        Returns
        -------
        out : KeypointsOnImage
            Shallow copy.

        """
        return copy.copy(self)

    def deepcopy(self):
        """
        Create a deep copy of the KeypointsOnImage object.

        Returns
        -------
        out : KeypointsOnImage
            Deep copy.

        """
        # for some reason deepcopy is way slower here than manual copy
        #return copy.deepcopy(self)
        kps = [Keypoint(x=kp.x, y=kp.y) for kp in self.keypoints]
        return KeypointsOnImage(kps, tuple(self.shape))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "KeypointsOnImage(%s, shape=%s)" % (str(self.keypoints), self.shape)

# TODO functions: square(), to_aspect_ratio(), extend()/add_border(), contains_point()
class BoundingBox(object):
    """
    Class representing bounding boxes.

    Each bounding box is parameterized by its top left and bottom right corners. Both are given
    as x and y-coordinates.

    Parameters
    ----------
    x1 : number
        X-coordinate of the top left of the bounding box.

    y1 : number
        Y-coordinate of the top left of the bounding box.

    x2 : number
        X-coordinate of the bottom right of the bounding box.

    y2 : number
        Y-coordinate of the bottom right of the bounding box.

    """

    def __init__(self, x1, y1, x2, y2, label=None):
        """Create a new BoundingBox instance."""
        if x1 > x2:
            x2, x1 = x1, x2
        do_assert(x2 > x1)
        if y1 > y2:
            y2, y1 = y1, y2
        do_assert(y2 > y1)

        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.label = label

    @property
    def x1_int(self):
        """
        Return the x-coordinate of the top left corner as an integer.

        Returns
        -------
        result : int
            X-coordinate of the top left corner, rounded to the closest integer.

        """
        return int(round(self.x1))

    @property
    def y1_int(self):
        """
        Return the y-coordinate of the top left corner as an integer.

        Returns
        -------
        result : int
            Y-coordinate of the top left corner, rounded to the closest integer.

        """
        return int(round(self.y1))

    @property
    def x2_int(self):
        """
        Return the x-coordinate of the bottom left corner as an integer.

        Returns
        -------
        result : int
            X-coordinate of the bottom left corner, rounded to the closest integer.

        """
        return int(round(self.x2))

    @property
    def y2_int(self):
        """
        Return the y-coordinate of the bottom left corner as an integer.

        Returns
        -------
        result : int
            Y-coordinate of the bottom left corner, rounded to the closest integer.

        """
        return int(round(self.y2))

    @property
    def height(self):
        """
        Estimate the height of the bounding box.

        Returns
        -------
        result : number
            Height of the bounding box.

        """
        return self.y2 - self.y1

    @property
    def width(self):
        """
        Estimate the width of the bounding box.

        Returns
        -------
        result : number
            Width of the bounding box.

        """
        return self.x2 - self.x1

    @property
    def center_x(self):
        """
        Estimate the x-coordinate of the center point of the bounding box.

        Returns
        -------
        result : number
            X-coordinate of the center point of the bounding box.

        """
        return self.x1 + self.width/2

    @property
    def center_y(self):
        """
        Estimate the y-coordinate of the center point of the bounding box.

        Returns
        -------
        result : number
            Y-coordinate of the center point of the bounding box.

        """
        return self.y1 + self.height/2

    @property
    def area(self):
        """
        Estimate the area of the bounding box.

        Returns
        -------
        result : number
            Area of the bounding box, i.e. `height * width`.

        """
        return self.height * self.width

    def project(self, from_shape, to_shape):
        """
        Project the bounding box onto a new position on a new image.

        E.g. if the bounding box is on its original image at
        x1=(10 of 100 pixels) and y1=(20 of 100 pixels) and is projected onto
        a new image with size (width=200, height=200), its new position will
        be (x1=20, y1=40). (Analogous for x2/y2.)

        This is intended for cases where the original image is resized.
        It cannot be used for more complex changes (e.g. padding, cropping).

        Parameters
        ----------
        from_shape : tuple
            Shape of the original image. (Before resize.)

        to_shape : tuple
            Shape of the new image. (After resize.)

        Returns
        -------
        out : BoundingBox
            BoundingBox object with new coordinates.

        """
        if from_shape[0:2] == to_shape[0:2]:
            return self.copy()
        else:
            from_height, from_width = from_shape[0:2]
            to_height, to_width = to_shape[0:2]
            do_assert(from_height > 0)
            do_assert(from_width > 0)
            do_assert(to_height > 0)
            do_assert(to_width > 0)
            x1 = (self.x1 / from_width) * to_width
            y1 = (self.y1 / from_height) * to_height
            x2 = (self.x2 / from_width) * to_width
            y2 = (self.y2 / from_height) * to_height
            return self.copy(
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                label=self.label
            )

    def extend(self, all_sides=0, top=0, right=0, bottom=0, left=0):
        """
        Extend the size of the bounding box along its sides.

        Parameters
        ----------
        all_sides : number, optional(default=0)
            Value by which to extend the bounding box size along all sides.

        top : number, optional(default=0)
            Value by which to extend the bounding box size along its top side.

        right : number, optional(default=0)
            Value by which to extend the bounding box size along its right side.

        bottom : number, optional(default=0)
            Value by which to extend the bounding box size along its bottom side.

        left : number, optional(default=0)
            Value by which to extend the bounding box size along its left side.

        Returns
        -------
        result : BoundingBox
            Extended bounding box.

        """
        return BoundingBox(
            x1=self.x1 - all_sides - left,
            x2=self.x2 + all_sides + right,
            y1=self.y1 - all_sides - top,
            y2=self.y2 + all_sides + bottom
        )

    def intersection(self, other, default=None):
        """
        Compute the intersection bounding box of this bounding box and another one.

        Parameters
        ----------
        other : BoundingBox
            Other bounding box with which to generate the intersection.

        Returns
        -------
        result : BoundingBox
            Intersection bounding box of the two bounding boxes.

        """
        x1_i = max(self.x1, other.x1)
        y1_i = max(self.y1, other.y1)
        x2_i = min(self.x2, other.x2)
        y2_i = min(self.y2, other.y2)
        if x1_i >= x2_i or y1_i >= y2_i:
            return default
        else:
            return BoundingBox(x1=x1_i, y1=y1_i, x2=x2_i, y2=y2_i)

    def union(self, other):
        """
        Compute the union bounding box of this bounding box and another one.

        This is equivalent to drawing a bounding box around all corners points of both
        bounding boxes.

        Parameters
        ----------
        other : BoundingBox
            Other bounding box with which to generate the union.

        Returns
        -------
        result : BoundingBox
            Union bounding box of the two bounding boxes.

        """
        return BoundingBox(
            x1=min(self.x1, other.x1),
            y1=min(self.y1, other.y1),
            x2=max(self.x2, other.x2),
            y2=max(self.y2, other.y2),
        )

    def iou(self, other):
        """
        Compute the IoU of this bounding box with another one.

        IoU is the intersection over union, defined as:
            area(intersection(A, B)) / area(union(A, B))
            = area(intersection(A, B)) / (area(A) + area(B) - area(intersection(A, B)))

        Parameters
        ----------
        other : BoundingBox
            Other bounding box with which to compare.

        Returns
        -------
        result : float
            IoU between the two bounding boxes.

        """
        inters = self.intersection(other)
        if inters is None:
            return 0
        else:
            return inters.area / (self.area + other.area - inters.area)

    def is_fully_within_image(self, image):
        """
        Estimate whether the bounding box is fully inside the image area.

        Parameters
        ----------
        image : (H,W,...) ndarray or tuple of at least two ints
            Image dimensions to use. If an ndarray, its shape will be used. If a tuple, it is
            assumed to represent the image shape.

        Returns
        -------
        result : bool
            True if the bounding box is fully inside the image area.
            False otherwise.

        """
        if isinstance(image, tuple):
            shape = image
        else:
            shape = image.shape
        height, width = shape[0:2]
        return self.x1 >= 0 and self.x2 <= width and self.y1 >= 0 and self.y2 <= height

    def is_partly_within_image(self, image):
        """
        Estimate whether the bounding box is at least partially inside the image area.

        Parameters
        ----------
        image : (H,W,...) ndarray or tuple of at least two ints
            Image dimensions to use. If an ndarray, its shape will be used. If a tuple, it is
            assumed to represent the image shape.

        Returns
        -------
        result : bool
            True if the bounding box is at least partially inside the image area.
            False otherwise.

        """
        if isinstance(image, tuple):
            shape = image
        else:
            shape = image.shape
        height, width = shape[0:2]
        img_bb = BoundingBox(x1=0, x2=width, y1=0, y2=height)
        return self.intersection(img_bb) is not None

    def is_out_of_image(self, image, fully=True, partly=False):
        """
        Estimate whether the bounding box is partially or fully outside of the image area.

        Parameters
        ----------
        image : (H,W,...) ndarray or tuple of ints
            Image dimensions to use. If an ndarray, its shape will be used. If a tuple, it is
            assumed to represent the image shape and must contain at least two integers.

        fully : bool, optional(default=True)
            Whether to return True if the bounding box is fully outside fo the image area.

        partly : bool, optional(default=False)
            Whether to return True if the bounding box is at least partially outside fo the
            image area.

        Returns
        -------
        result : bool
            True if the bounding box is partially/fully outside of the image area, depending
            on defined parameters. False otherwise.

        """
        if self.is_fully_within_image(image):
            return False
        elif self.is_partly_within_image(image):
            return partly
        else:
            return fully

    def cut_out_of_image(self, image):
        """
        Cut off all parts of the bounding box that are outside of the image.

        Parameters
        ----------
        image : (H,W,...) ndarray or tuple of at least two ints
            Image dimensions to use for the clipping of the bounding box. If an ndarray, its
            shape will be used. If a tuple, it is assumed to represent the image shape.

        Returns
        -------
        result : BoundingBox
            Bounding box, clipped to fall within the image dimensions.

        """
        if isinstance(image, tuple):
            shape = image
        else:
            shape = image.shape

        height, width = shape[0:2]
        do_assert(height > 0)
        do_assert(width > 0)

        x1 = np.clip(self.x1, 0, width)
        x2 = np.clip(self.x2, 0, width)
        y1 = np.clip(self.y1, 0, height)
        y2 = np.clip(self.y2, 0, height)

        return self.copy(
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            label=self.label
        )

    def shift(self, top=None, right=None, bottom=None, left=None):
        """
        Shift the bounding box from one or more image sides, i.e. move it on the x/y-axis.

        Parameters
        ----------
        top : None or int, optional(default=None)
            Amount of pixels by which to shift the bounding box from the top.

        right : None or int, optional(default=None)
            Amount of pixels by which to shift the bounding box from the right.

        bottom : None or int, optional(default=None)
            Amount of pixels by which to shift the bounding box from the bottom.

        left : None or int, optional(default=None)
            Amount of pixels by which to shift the bounding box from the left.

        Returns
        -------
        result : BoundingBox
            Shifted bounding box.

        """
        top = top if top is not None else 0
        right = right if right is not None else 0
        bottom = bottom if bottom is not None else 0
        left = left if left is not None else 0
        return self.copy(
            x1=self.x1+left-right,
            x2=self.x2+left-right,
            y1=self.y1+top-bottom,
            y2=self.y2+top-bottom
        )

    def draw_on_image(self, image, color=[0, 255, 0], alpha=1.0, thickness=1, copy=True, raise_if_out_of_image=False): # pylint: disable=locally-disabled, dangerous-default-value, line-too-long
        """
        Draw the bounding box on an image.

        Parameters
        ----------
        image : (H,W,C) ndarray(uint8)
            The image onto which to draw the bounding box.

        color : iterable of int, optional(default=[0,255,0])
            The color to use, corresponding to the channel layout of the image. Usually RGB.

        alpha : float, optional(default=1.0)
            The transparency of the drawn bounding box, where 1.0 denotes no transparency and
            0.0 is invisible.

        thickness : int, optional(default=1)
            The thickness of the bounding box in pixels. If the value is larger than 1, then
            additional pixels will be added around the bounding box (i.e. extension towards the
            outside).

        copy : bool, optional(default=True)
            Whether to copy the input image or change it in-place.

        raise_if_out_of_image : bool, optional(default=False)
            Whether to raise an error if the bounding box is partially/fully outside of the
            image. If set to False, no error will be raised and only the parts inside the image
            will be drawn.

        Returns
        -------
        result : (H,W,C) ndarray(uint8)
            Image with bounding box drawn on it.

        """
        if raise_if_out_of_image and self.is_out_of_image(image):
            raise Exception("Cannot draw bounding box x1=%.8f, y1=%.8f, x2=%.8f, y2=%.8f on image with shape %s." % (self.x1, self.y1, self.x2, self.y2, image.shape))

        result = np.copy(image) if copy else image

        if isinstance(color, (tuple, list)):
            color = np.uint8(color)

        for i in range(thickness):
            y = [self.y1_int-i, self.y1_int-i, self.y2_int+i, self.y2_int+i]
            x = [self.x1_int-i, self.x2_int+i, self.x2_int+i, self.x1_int-i]
            rr, cc = skimage.draw.polygon_perimeter(y, x, shape=result.shape)
            if alpha >= 0.99:
                result[rr, cc, :] = color
            else:
                if is_float_array(result):
                    result[rr, cc, :] = (1 - alpha) * result[rr, cc, :] + alpha * color
                    result = np.clip(result, 0, 255)
                else:
                    input_dtype = result.dtype
                    result = result.astype(np.float32)
                    result[rr, cc, :] = (1 - alpha) * result[rr, cc, :] + alpha * color
                    result = np.clip(result, 0, 255).astype(input_dtype)

        return result

    def extract_from_image(self, image):
        """
        Extract the image pixels within the bounding box.

        This function will zero-pad the image if the bounding box is partially/fully outside of
        the image.

        Parameters
        ----------
        image : (H,W) or (H,W,C) ndarray
            The image from which to extract the pixels within the bounding box.

        Returns
        -------
        result : (H',W') or (H',W',C) ndarray
            Pixels within the bounding box. Zero-padded if the bounding box is partially/fully
            outside of the image.

        """
        pad_top = 0
        pad_right = 0
        pad_bottom = 0
        pad_left = 0

        height, width = image.shape[0], image.shape[1]
        x1, x2, y1, y2 = self.x1_int, self.x2_int, self.y1_int, self.y2_int

        # if the bb is outside of the image area, the following pads the image
        # first with black pixels until the bb is inside the image
        # and only then extracts the image area
        # TODO probably more efficient to initialize an array of zeros
        # and copy only the portions of the bb into that array that are
        # natively inside the image area
        if x1 < 0:
            pad_left = abs(x1)
            x2 = x2 + abs(x1)
            x1 = 0
        if y1 < 0:
            pad_top = abs(y1)
            y2 = y2 + abs(y1)
            y1 = 0
        if x2 >= width:
            pad_right = x2 - (width - 1)
        if y2 >= height:
            pad_bottom = y2 - (height - 1)

        if any([val > 0 for val in [pad_top, pad_right, pad_bottom, pad_left]]):
            if len(image.shape) == 2:
                image = np.pad(image, ((pad_top, pad_bottom), (pad_left, pad_right)), mode="constant")
            else:
                image = np.pad(image, ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)), mode="constant")

        return image[y1:y2, x1:x2]

    # TODO also add to_heatmap
    # TODO add this to BoundingBoxesOnImage
    def to_keypoints(self):
        """
        Convert the corners of the bounding box to keypoints (clockwise, starting at top left).

        Returns
        -------
        result : list of Keypoint
            Corners of the bounding box as keypoints.
        """
        return [
            Keypoint(x=self.x1, y=self.y1),
            Keypoint(x=self.x2, y=self.y1),
            Keypoint(x=self.x2, y=self.y2),
            Keypoint(x=self.x1, y=self.y2)
        ]

    def copy(self, x1=None, y1=None, x2=None, y2=None, label=None):
        """
        Create a shallow copy of the BoundingBox object.

        Parameters
        ----------
        x1 : None or number
            If not None, then the x1 coordinate of the copied object will be set to this value.

        y1 : None or number
            If not None, then the y1 coordinate of the copied object will be set to this value.

        x2 : None or number
            If not None, then the x2 coordinate of the copied object will be set to this value.

        y2 : None or number
            If not None, then the y2 coordinate of the copied object will be set to this value.

        label : None or string
            If not None, then the label of the copied object will be set to this value.

        Returns
        -------
        result : BoundingBox
            Shallow copy.

        """
        return BoundingBox(
            x1=self.x1 if x1 is None else x1,
            x2=self.x2 if x2 is None else x2,
            y1=self.y1 if y1 is None else y1,
            y2=self.y2 if y2 is None else y2,
            label=self.label if label is None else label
        )

    def deepcopy(self, x1=None, y1=None, x2=None, y2=None, label=None):
        """
        Create a deep copy of the BoundingBoxesOnImage object.

        Returns
        -------
        out : KeypointsOnImage
            Deep copy.

        """
        return self.copy(x1=x1, y1=y1, x2=x2, y2=y2, label=label)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "BoundingBox(x1=%.4f, y1=%.4f, x2=%.4f, y2=%.4f, label=%s)" % (self.x1, self.y1, self.x2, self.y2, self.label)

class BoundingBoxesOnImage(object):
    """
    Object that represents all bounding boxes on a single image.

    Parameters
    ----------
    bounding_boxes : list of BoundingBox
        List of bounding boxes on the image.

    shape : tuple of int
        The shape of the image on which the bounding boxes are placed.

    Examples
    --------
    >>> bbs = [
    >>>     BoundingBox(x1=10, y1=20, x2=20, y2=30),
    >>>     BoundingBox(x1=25, y1=50, x2=30, y2=70)
    >>> ]
    >>> bbs_oi = BoundingBoxesOnImage(bbs, shape=image.shape)

    """
    def __init__(self, bounding_boxes, shape):
        self.bounding_boxes = bounding_boxes
        if is_np_array(shape):
            self.shape = shape.shape
        else:
            do_assert(isinstance(shape, (tuple, list)))
            self.shape = tuple(shape)

    @property
    def height(self):
        """
        Get the height of the image on which the bounding boxes fall.

        Returns
        -------
        result : int
            Image height.

        """
        return self.shape[0]

    @property
    def width(self):
        """
        Get the width of the image on which the bounding boxes fall.

        Returns
        -------
        result : int
            Image width.

        """
        return self.shape[1]

    @property
    def empty(self):
        """
        Returns whether this object contains zero bounding boxes.

        Returns
        -------
        result : bool
            True if this object contains zero bounding boxes.
        """
        return len(self.bounding_boxes) == 0

    def on(self, image):
        """
        Project bounding boxes from one image to a new one.

        Parameters
        ----------
        image : ndarray or tuple
            New image onto which the bounding boxes are to be projected.
            May also simply be that new image's shape tuple.

        Returns
        -------
        keypoints : BoundingBoxesOnImage
            Object containing all projected bounding boxes.

        """
        if is_np_array(image):
            shape = image.shape
        else:
            shape = image

        if shape[0:2] == self.shape[0:2]:
            return self.deepcopy()
        else:
            bounding_boxes = [bb.project(self.shape, shape) for bb in self.bounding_boxes]
            return BoundingBoxesOnImage(bounding_boxes, shape)

    def draw_on_image(self, image, color=[0, 255, 0], alpha=1.0, thickness=1, copy=True, raise_if_out_of_image=False):
        """
        Draw all bounding boxes onto a given image.

        Parameters
        ----------
        image : (H,W,3) ndarray
            The image onto which to draw the bounding boxes.
            This image should usually have the same shape as
            set in BoundingBoxesOnImage.shape.

        color : int or list of ints or tuple of ints or (3,) ndarray, optional(default=[0, 255, 0])
            The RGB color of all bounding boxes. If a single int `C`, then that is
            equivalent to (C,C,C).

        size : float, optional(default=1.0)
            Alpha/transparency of the bounding box.

        thickness : int, optional(default=1)
            Thickness in pixels.

        copy : bool, optional(default=True)
            Whether to copy the image before drawing the points.

        raise_if_out_of_image : bool, optional(default=False)
            Whether to raise an exception if any bounding box is outside of the
            image.

        Returns
        -------
        image : (H,W,3) ndarray
            Image with drawn bounding boxes.

        """
        for bb in self.bounding_boxes:
            image = bb.draw_on_image(
                image,
                color=color,
                alpha=alpha,
                thickness=thickness,
                copy=copy,
                raise_if_out_of_image=raise_if_out_of_image
            )

        return image

    def remove_out_of_image(self, fully=True, partly=False):
        """
        Remove all bounding boxes that are fully or partially outside of the image.

        Parameters
        ----------
        fully : bool, optional(default=True)
            Whether to remove bounding boxes that are fully outside of the image.

        partly : bool, optional(default=False)
            Whether to remove bounding boxes that are partially outside of the image.

        Returns
        -------
        result : BoundingBoxesOnImage
            Reduced set of bounding boxes, with those that were fully/partially outside of
            the image removed.

        """
        bbs_clean = [bb for bb in self.bounding_boxes if not bb.is_out_of_image(self.shape, fully=fully, partly=partly)]
        return BoundingBoxesOnImage(bbs_clean, shape=self.shape)

    def cut_out_of_image(self):
        """
        Cut off all parts from all bounding boxes that are outside of the image.

        Returns
        -------
        result : BoundingBoxesOnImage
            Bounding boxes, clipped to fall within the image dimensions.

        """
        bbs_cut = [bb.cut_out_of_image(self.shape) for bb in self.bounding_boxes if bb.is_partly_within_image(self.shape)]
        return BoundingBoxesOnImage(bbs_cut, shape=self.shape)

    def shift(self, top=None, right=None, bottom=None, left=None):
        """
        Shift all bounding boxes from one or more image sides, i.e. move them on the x/y-axis.

        Parameters
        ----------
        top : None or int, optional(default=None)
            Amount of pixels by which to shift all bounding boxes from the top.

        right : None or int, optional(default=None)
            Amount of pixels by which to shift all bounding boxes from the right.

        bottom : None or int, optional(default=None)
            Amount of pixels by which to shift all bounding boxes from the bottom.

        left : None or int, optional(default=None)
            Amount of pixels by which to shift all bounding boxes from the left.

        Returns
        -------
        result : BoundingBoxesOnImage
            Shifted bounding boxes.

        """
        bbs_new = [bb.shift(top=top, right=right, bottom=bottom, left=left) for bb in self.bounding_boxes]
        return BoundingBoxesOnImage(bbs_new, shape=self.shape)

    def copy(self):
        """
        Create a shallow copy of the BoundingBoxesOnImage object.

        Returns
        -------
        out : BoundingBoxesOnImage
            Shallow copy.

        """
        return copy.copy(self)

    def deepcopy(self):
        """
        Create a deep copy of the BoundingBoxesOnImage object.

        Returns
        -------
        out : KeypointsOnImage
            Deep copy.

        """
        # Manual copy is far faster than deepcopy for KeypointsOnImage,
        # so use manual copy here too
        bbs = [bb.deepcopy() for bb in self.bounding_boxes]
        return BoundingBoxesOnImage(bbs, tuple(self.shape))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "BoundingBoxesOnImage(%s, shape=%s)" % (str(self.bounding_boxes), self.shape)


class HeatmapsOnImage(object):
    """
    Object representing heatmaps on images.

    Parameters
    ----------
    arr : (H,W) or (H,W,C) ndarray(float32)
        Array representing the heatmap(s). If multiple heatmaps, then C is expected to denote
        their number.

    shape : tuple of ints
        Shape of the image on which the heatmap(s) is/are placed. NOT the shape of the
        heatmap(s) array, unless it is identical to the image shape (note the likely
        difference between the arrays in the number of channels).
        If there is not a corresponding image, use the shape of the heatmaps array.

    min_value : float, optional(default=0.0)
        Minimum value for the heatmaps that `arr` represents. This will usually
        be 0.0.

    max_value : float, optional(default=1.0)
        Maximum value for the heatmaps that `arr` represents. This will usually
        be 1.0.

    """

    def __init__(self, arr, shape, min_value=0.0, max_value=1.0):
        """Construct a new HeatmapsOnImage object."""
        assert arr.dtype.type in [np.float32]
        assert arr.ndim in [2, 3]
        assert len(shape) in [2, 3]
        assert min_value < max_value
        assert np.min(arr.flat[0:50]) >= min_value - np.finfo(arr.dtype).eps
        assert np.max(arr.flat[0:50]) <= max_value + np.finfo(arr.dtype).eps

        if arr.ndim == 2:
            arr = arr[..., np.newaxis]
            self.arr_was_2d = True
        else:
            self.arr_was_2d = False

        eps = np.finfo(np.float32).eps
        min_is_zero = 0.0 - eps  < min_value < 0.0 + eps
        max_is_one = 1.0 - eps < max_value < 1.0 + eps
        if min_is_zero and max_is_one:
            self.arr_0to1 = arr
        else:
            self.arr_0to1 = (arr - min_value) / (max_value - min_value)
        self.shape = shape
        self.min_value = min_value
        self.max_value = max_value

    def get_arr(self):
        """
        Get the heatmap array in the desired value range.

        The HeatmapsOnImage object saves heatmaps internally in the value range (min=0.0, max=1.0).
        This function converts the internal representation to (min=min_value, max=max_value),
        where min_value and max_value are provided upon instantiation of the object.

        Returns
        -------
        result : (H,W) or (H,W,C) ndarray(float32)
            Heatmap array.

        """
        if self.arr_was_2d and self.arr_0to1.shape[2] == 1:
            arr = self.arr_0to1[:, :, 0]
        else:
            arr = self.arr_0to1

        eps = np.finfo(np.float32).eps
        min_is_zero = 0.0 - eps < self.min_value < 0.0 + eps
        max_is_one = 1.0 - eps < self.max_value < 1.0 + eps
        if min_is_zero and max_is_one:
            return np.copy(arr)
        else:
            diff = self.max_value - self.min_value
            return self.min_value + diff * arr

    # TODO
    #def find_global_maxima(self):
    #    raise NotImplementedError()

    def draw(self, size=None, cmap="jet"):
        """
        Render the heatmaps as RGB images.

        Parameters
        ----------
        size : None or float or iterable of two ints or iterable of two floats, optional(default=None)
            Size of the rendered RGB image as (height, width).
            See `imresize_single_image()` for details.
            If set to None, no resizing is performed and the size of the heatmaps array is used.

        cmap : string or None, optional(default="jet")
            Color map of matplotlib to use in order to convert the heatmaps into RGB images.
            If set to None, no color map will be used and the heatmaps will be converted
            as simple intensity maps.

        Returns
        -------
        heatmaps_drawn : list of (H,W,3) ndarray(uint8)
            Rendered heatmaps, one per heatmap array channel.

        """
        heatmaps_uint8 = self.to_uint8()
        heatmaps_drawn = []

        for c in sm.xrange(heatmaps_uint8.shape[2]):
            # c:c+1 here, because the additional axis is needed by imresize_single_image
            heatmap_c = heatmaps_uint8[..., c:c+1]

            if size is not None:
                heatmap_c_rs = imresize_single_image(heatmap_c, size,
                                                     interpolation="nearest")
            else:
                heatmap_c_rs = heatmap_c
            heatmap_c_rs = np.squeeze(heatmap_c_rs).astype(np.float32) / 255.0

            if cmap is not None:
                import matplotlib.pyplot as plt

                cmap_func = plt.get_cmap(cmap)
                heatmap_cmapped = cmap_func(heatmap_c_rs)
                heatmap_cmapped = np.delete(heatmap_cmapped, 3, 2)
            else:
                heatmap_cmapped = np.tile(heatmap_c_rs[..., np.newaxis], (1, 1, 3))

            heatmap_cmapped = np.clip(heatmap_cmapped * 255, 0, 255).astype(np.uint8)

            heatmaps_drawn.append(heatmap_cmapped)
        return heatmaps_drawn

    def draw_on_image(self, image, alpha=0.75, cmap="jet", resize="heatmaps"):
        """
        Draw the heatmaps as overlays over an image.

        Parameters
        ----------
        image : (H,W,3) ndarray(uint8)
            Image onto which to draw the heatmaps.

        alpha : float, optional(default=0.75)
            Alpha/opacity value to use for the mixing of image and heatmaps.
            Higher values mean that the heatmaps will be more visible and the image less visible.

        cmap : string or None, optional(default="jet")
            Color map to use. See `HeatmapsOnImage.draw()` for details.

        resize : "heatmaps" or "image", optional(default="heatmaps")
            In case of size differences between the image and heatmaps, either the image or
            the heatmaps can be resized. This parameter controls which of the two will be resized
            to the other's size.

        Returns
        -------
        mix : list of (H,W,3) ndarray(uint8)
            Rendered overlays, one per heatmap array channel.

        """
        # assert RGB image
        assert image.ndim == 3
        assert image.shape[2] == 3
        assert image.dtype.type == np.uint8

        assert 0 - 1e-8 <= alpha <= 1.0 + 1e-8
        assert resize in ["heatmaps", "image"]

        if resize == "image":
            image = imresize_single_image(image, self.arr_0to1.shape[0:2], interpolation="cubic")

        heatmaps_drawn = self.draw(
            size=image.shape[0:2] if resize == "heatmaps" else None,
            cmap=cmap
        )

        mix = [
            np.clip((1-alpha) * image + alpha * heatmap_i, 0, 255).astype(np.uint8)
            for heatmap_i
            in heatmaps_drawn
        ]

        return mix

    def pad(self, top=0, right=0, bottom=0, left=0, mode="constant", cval=0.0):
        """
        Pad the heatmaps on their top/right/bottom/left side.

        Parameters
        ----------
        top : int, optional(default=0)
            Amount of pixels to add at the top side of the heatmaps. Must be 0 or greater.

        right : int, optional(default=0)
            Amount of pixels to add at the right side of the heatmaps. Must be 0 or greater.

        bottom : int, optional(default=0)
            Amount of pixels to add at the bottom side of the heatmaps. Must be 0 or greater.

        left : int, optional(default=0)
            Amount of pixels to add at the left side of the heatmaps. Must be 0 or greater.

        mode : string, optional(default="constant")
            Padding mode to use. See `numpy.pad()` for details.

        cval : number, optional(default=0.0)
            Value to use for padding if mode="constant". See `numpy.pad()` for details.

        Returns
        -------
        result : HeatmapsOnImage
            Padded heatmaps of height H'=H+top+bottom and width W'=W+left+right.

        """
        arr_0to1_padded = pad(self.arr_0to1, top=top, right=right, bottom=bottom, left=left, mode=mode, cval=cval)
        return HeatmapsOnImage.from_0to1(arr_0to1_padded, shape=self.shape, min_value=self.min_value, max_value=self.max_value)

    def pad_to_aspect_ratio(self, aspect_ratio, mode="constant", cval=0.0, return_pad_amounts=False):
        """
        Pad the heatmaps on their sides so that they match a target aspect ratio.

        Depending on which dimension is smaller (height or width), only the corresponding
        sides (left/right or top/bottom) will be padded. In each case, both of the sides will
        be padded equally.

        Parameters
        ----------
        aspect_ratio : float
            Target aspect ratio, given as width/height. E.g. 2.0 denotes the image having twice
            as much width as height.

        mode : string, optional(default="constant")
            Padding mode to use. See `numpy.pad()` for details.

        cval : number, optional(default=0.0)
            Value to use for padding if mode="constant". See `numpy.pad()` for details.

        return_pad_amounts : bool, optional(default=False)
            If False, then only the padded image will be returned. If True, a tuple with two
            entries will be returned, where the first entry is the padded image and the second
            entry are the amounts by which each image side was padded. These amounts are again a
            tuple of the form (top, right, bottom, left), with each value being an integer.

        Returns
        -------
        result : tuple
            First tuple entry: Padded heatmaps as HeatmapsOnImage object.
            Second tuple entry: Amounts by which the heatmaps were padded on each side, given
            as a tuple (top, right, bottom, left).
            If return_pad_amounts is False, then only the heatmaps object is returned.

        """
        arr_0to1_padded, pad_amounts = pad_to_aspect_ratio(self.arr_0to1, aspect_ratio=aspect_ratio, mode=mode, cval=cval, return_pad_amounts=True)
        heatmaps = HeatmapsOnImage.from_0to1(arr_0to1_padded, shape=self.shape, min_value=self.min_value, max_value=self.max_value)
        if return_pad_amounts:
            return heatmaps, pad_amounts
        else:
            return heatmaps

    def avg_pool(self, block_size):
        """
        Rescale the heatmap(s) array using average pooling of a given block/kernel size.

        Parameters
        ----------
        block_size : int or tuple of two ints or tuple of three ints
            Size of each block of values to pool, aka kernel size. See `imgaug.pool()` for details.

        Returns
        -------
        result : HeatmapsOnImage
            Heatmaps after average pooling.

        """
        arr_0to1_reduced = avg_pool(self.arr_0to1, block_size, cval=0.0)
        return HeatmapsOnImage.from_0to1(arr_0to1_reduced, shape=self.shape, min_value=self.min_value, max_value=self.max_value)

    def max_pool(self, block_size):
        """
        Rescale the heatmap(s) array using max-pooling of a given block/kernel size.

        Parameters
        ----------
        block_size : int or tuple of two ints or tuple of three ints
            Size of each block of values to pool, aka kernel size. See `imgaug.pool()` for details.

        Returns
        -------
        result : HeatmapsOnImage
            Heatmaps after max-pooling.

        """
        arr_0to1_reduced = max_pool(self.arr_0to1, block_size)
        return HeatmapsOnImage.from_0to1(arr_0to1_reduced, shape=self.shape, min_value=self.min_value, max_value=self.max_value)

    def scale(self, sizes, interpolation="cubic"):
        """
        Rescale the heatmap(s) array to the provided size given the provided interpolation.

        Parameters
        ----------
        sizes : float or iterable of two ints or iterable of two floats
            New size of the array in (height, width). See `imresize_single_image()` for details.

        interpolation : None or string or int, optional(default="cubic")
            The interpolation to use during resize. See `imresize_single_image()` for details.

        Returns
        -------
        result : HeatmapsOnImage
            Rescaled heatmaps object.

        """
        arr_0to1_rescaled = imresize_single_image(self.arr_0to1, sizes, interpolation=interpolation)

        # cubic interpolation can lead to values outside of [0.0, 1.0],
        # see https://github.com/opencv/opencv/issues/7195
        # TODO area interpolation too?
        arr_0to1_rescaled = np.clip(arr_0to1_rescaled, 0.0, 1.0)

        return HeatmapsOnImage.from_0to1(arr_0to1_rescaled, shape=self.shape, min_value=self.min_value, max_value=self.max_value)

    def to_uint8(self):
        """
        Convert this heatmaps object to a 0-to-255 array.

        Returns
        -------
        arr_uint8 : (H,W,C) ndarray(uint8)
            Heatmap as a 0-to-255 array.

        """
        # TODO this always returns (H,W,C), even if input ndarray was originall (H,W)
        # does it make sense here to also return (H,W) if self.arr_was_2d?
        arr_0to255 = np.clip(np.round(self.arr_0to1 * 255), 0, 255)
        arr_uint8 = arr_0to255.astype(np.uint8)
        return arr_uint8

    @staticmethod
    def from_uint8(arr_uint8, shape, min_value=0.0, max_value=1.0):
        """
        Create a heatmaps object from an heatmap array containing values ranging from 0 to 255.

        Parameters
        ----------
        arr_uint8 : (H,W) or (H,W,C) ndarray(uint8)
            Heatmap(s) array, where H=height, W=width, C=heatmap channels.

        shape : tuple of ints
            Shape of the image on which the heatmap(s) is/are placed. NOT the shape of the
            heatmap(s) array, unless it is identical to the image shape (note the likely
            difference between the arrays in the number of channels).
            If there is not a corresponding image, use the shape of the heatmaps array.

        min_value : float, optional(default=0.0)
            Minimum value for the heatmaps that the 0-to-255 array represents. This will usually
            be 0.0. It is used when calling `HeatmapsOnImage.get_arr()`, which converts the
            underlying (0, 255) array to value range (min_value, max_value).

        max_value : float, optional(default=1.0)
            Maximum value for the heatmaps that 0-to-255 array represents.
            See parameter min_value for details.

        Returns
        -------
        heatmaps : HeatmapsOnImage
            Heatmaps object.

        """
        arr_0to1 = arr_uint8.astype(np.float32) / 255.0
        return HeatmapsOnImage.from_0to1(arr_0to1, shape, min_value=min_value, max_value=max_value)

    @staticmethod
    def from_0to1(arr_0to1, shape, min_value=0.0, max_value=1.0):
        """
        Create a heatmaps object from an heatmap array containing values ranging from 0.0 to 1.0.

        Parameters
        ----------
        arr_0to1 : (H,W) or (H,W,C) ndarray(float32)
            Heatmap(s) array, where H=height, W=width, C=heatmap channels.

        shape : tuple of ints
            Shape of the image on which the heatmap(s) is/are placed. NOT the shape of the
            heatmap(s) array, unless it is identical to the image shape (note the likely
            difference between the arrays in the number of channels).
            If there is not a corresponding image, use the shape of the heatmaps array.

        min_value : float, optional(default=0.0)
            Minimum value for the heatmaps that the 0-to-1 array represents. This will usually
            be 0.0. It is used when calling `HeatmapsOnImage.get_arr()`, which converts the
            underlying (0.0, 1.0) array to value range (min_value, max_value).
            E.g. if you started with heatmaps in the range (-1.0, 1.0) and projected these
            to (0.0, 1.0), you should call this function with min_value=-1.0, max_value=1.0
            so that `get_arr()` returns heatmap arrays having value range (-1.0, 1.0).

        max_value : float, optional(default=1.0)
            Maximum value for the heatmaps that to 0-to-255 array represents.
            See parameter min_value for details.

        Returns
        -------
        heatmaps : HeatmapsOnImage
            Heatmaps object.

        """
        heatmaps = HeatmapsOnImage(arr_0to1, shape, min_value=0.0, max_value=1.0)
        heatmaps.min_value = min_value
        heatmaps.max_value = max_value
        return heatmaps

    @staticmethod
    def change_normalization(arr, source, target):
        """
        Change the value range of a heatmap from one min-max to another min-max.

        E.g. the value range may be changed from min=0.0, max=1.0 to min=-1.0, max=1.0.

        Parameters
        ----------
        arr : ndarray
            Heatmap array to modify.

        source : tuple of two floats
            Current value range of the input array, given as (min, max), where both are float
            values.

        target : tuple of two floats
            Desired output value range of the array, given as (min, max), where both are float
            values.

        Returns
        -------
        arr_target : ndarray
            Input array, with value range projected to the desired target value range.

        """
        assert is_np_array(arr)

        if isinstance(source, HeatmapsOnImage):
            source = (source.min_value, source.max_value)
        else:
            assert isinstance(source, tuple)
            assert len(source) == 2
            assert source[0] < source[1]

        if isinstance(target, HeatmapsOnImage):
            target = (target.min_value, target.max_value)
        else:
            assert isinstance(target, tuple)
            assert len(target) == 2
            assert target[0] < target[1]

        # Check if source and target are the same (with a tiny bit of tolerance)
        # if so, evade compuation and just copy the array instead.
        # This is reasonable, as source and target will often both be (0.0, 1.0).
        eps = np.finfo(arr.dtype).eps
        mins_same = source[0] - 10*eps < target[0] < source[0] + 10*eps
        maxs_same = source[1] - 10*eps < target[1] < source[1] + 10*eps
        if mins_same and maxs_same:
            return np.copy(arr)

        min_source, max_source = source
        min_target, max_target = target

        diff_source = max_source - min_source
        diff_target = max_target - min_target

        arr_0to1 = (arr - min_source) / diff_source
        arr_target = min_target + arr_0to1 * diff_target

        return arr_target

    def copy(self):
        """
        Create a shallow copy of the Heatmaps object.

        Returns
        -------
        out : HeatmapsOnImage
            Shallow copy.

        """
        return self.deepcopy()

    def deepcopy(self):
        """
        Create a deep copy of the Heatmaps object.

        Returns
        -------
        out : HeatmapsOnImage
            Deep copy.

        """
        return HeatmapsOnImage(self.get_arr(), shape=self.shape, min_value=self.min_value, max_value=self.max_value)


class SegmentationMapOnImage(object):
    """
    Object representing a segmentation map associated with an image.

    Attributes
    ----------
    DEFAULT_SEGMENT_COLORS : list of tuple of int
        Standard RGB colors to use during drawing, ordered by class index.

    Parameters
    ----------
    arr : (H,W) ndarray or (H,W,1) ndarray or (H,W,C) ndarray
        Array representing the segmentation map. May have datatypes bool, integer or float.

            * If bool: Assumed to be of shape (H,W), (H,W,1) or (H,W,C). If (H,W) or (H,W,1) it
              is assumed to be for the case of having a single class (where any False denotes
              background). Otherwise there are assumed to be C channels, one for each class,
              with each of them containing a mask for that class. The masks may overlap.
            * If integer: Assumed to be of shape (H,W) or (H,W,1). Each pixel is assumed to
              contain an integer denoting the class index. Classes are assumed to be
              non-overlapping. The number of classes cannot be guessed from this input, hence
              nb_classes must be set.
            * If float: Assumed to b eof shape (H,W), (H,W,1) or (H,W,C) with meanings being
              similar to the case of `bool`. Values are expected to fall always in the range
              0.0 to 1.0 and are usually expected to be either 0.0 or 1.0 upon instantiation
              of a new segmentation map. Classes may overlap.

    shape : iterable of int
        Shape of the corresponding image (NOT the segmentation map array). This is expected
        to be (H, W) or (H, W, C) with C usually being 3. If there is no corresponding image,
        then use the segmentation map's shape instead.

    nb_classes : int or None
        Total number of unique classes that may appear in an segmentation map, i.e. the max
        class index. This may be None if the input array is of type bool or float. The number
        of class however must be provided if the input array is of type int, as then the
        number of classes cannot be guessed.

    """

    DEFAULT_SEGMENT_COLORS = [
        (0, 0, 0),  # black
        (230, 25, 75),  # red
        (60, 180, 75),  # green
        (255, 225, 25),  # yellow
        (0, 130, 200),  # blue
        (245, 130, 48),  # orange
        (145, 30, 180),  # purple
        (70, 240, 240),  # cyan
        (240, 50, 230),  # magenta
        (210, 245, 60),  # lime
        (250, 190, 190),  # pink
        (0, 128, 128),  # teal
        (230, 190, 255),  # lavender
        (170, 110, 40),  # brown
        (255, 250, 200),  # beige
        (128, 0, 0),  # maroon
        (170, 255, 195),  # mint
        (128, 128, 0),  # olive
        (255, 215, 180),  # coral
        (0, 0, 128),  # navy
        (128, 128, 128),  # grey
        (255, 255, 255),  # white
        # --
        (115, 12, 37),  # dark red
        (30, 90, 37),  # dark green
        (127, 112, 12),  # dark yellow
        (0, 65, 100),  # dark blue
        (122, 65, 24),  # dark orange
        (72, 15, 90),  # dark purple
        (35, 120, 120),  # dark cyan
        (120, 25, 115),  # dark magenta
        (105, 122, 30),  # dark lime
        (125, 95, 95),  # dark pink
        (0, 64, 64),  # dark teal
        (115, 95, 127),  # dark lavender
        (85, 55, 20),  # dark brown
        (127, 125, 100),  # dark beige
        (64, 0, 0),  # dark maroon
        (85, 127, 97),  # dark mint
        (64, 64, 0),  # dark olive
        (127, 107, 90),  # dark coral
        (0, 0, 64),  # dark navy
        (64, 64, 64),  # dark grey
    ]

    def __init__(self, arr, shape, nb_classes=None):
        if arr.dtype.type == np.bool:
            assert arr.ndim in [2, 3]
            self.input_was = ("bool", arr.ndim)
            if arr.ndim == 2:
                arr = arr[..., np.newaxis]
            arr = arr.astype(np.float32)
        elif arr.dtype.type in [np.uint8, np.uint32, np.int8, np.int16, np.int32]:
            assert arr.ndim == 2 or (arr.ndim == 3 and arr.shape[2] == 1)
            assert nb_classes is not None
            assert nb_classes > 0
            assert np.min(arr.flat[0:100]) >= 0
            assert np.max(arr.flat[0:100]) <= nb_classes
            self.input_was = ("int", arr.dtype.type, arr.ndim)
            if arr.ndim == 3:
                arr = arr[..., 0]
            arr = np.eye(nb_classes)[arr]  # from class indices to one hot
            arr = arr.astype(np.float32)
        elif arr.dtype.type in [np.float16, np.float32]:
            assert arr.ndim == 3
            self.input_was = ("float", arr.dtype.type, arr.ndim)
            arr = arr.astype(np.float32)
        else:
            dt = str(arr.dtype) if is_np_array(arr) else "<no ndarray>"
            raise Exception("Input was expected to be an ndarray of dtype bool, uint8, uint32 "
                            "int8, int16, int32 or float32. Got type %s with dtype %s." % (type(arr), dt))
        assert arr.ndim == 3
        assert arr.dtype.type == np.float32
        self.arr = arr
        self.shape = shape
        self.nb_classes = nb_classes if nb_classes is not None else arr.shape[2]

    #@property
    #def nb_classes(self):
    #    return self.arr.shape[2]

    def get_arr_int(self, background_threshold=0.01, background_class_id=0):
        """
        Get the segmentation map array as an integer array of shape (H, W).

        Each pixel in that array contains an integer value representing the pixel's class.
        If multiple classes overlap, the one with the highest local float value is picked.
        If that highest local value is below `background_threshold`, the method instead uses
        the background class id as the pixel's class value.

        Parameters
        ----------
        background_threshold : float, optional(default=0.01)
            At each pixel, each class-heatmap has a value between 0.0 and 1.0. If none of the
            class-heatmaps has a value above this threshold, the method uses the background class
            id instead.

        background_class_id : int, optional(default=0)
            Class id to fall back to if no class-heatmap passes the threshold at a spatial
            location.

        Returns
        -------
        result : (H,W) ndarray(int)
            Segmentation map array.

        """
        channelwise_max_idx = np.argmax(self.arr, axis=2)
        result = channelwise_max_idx
        if background_threshold is not None and background_threshold > 0:
            probs = np.amax(self.arr, axis=2)
            result[probs < background_threshold] = background_class_id
        return result.astype(np.int32)

    #def get_arr_bool(self, allow_overlapping=False, threshold=0.5, background_threshold=0.01, background_class_id=0):
    #    # TODO
    #    raise NotImplementedError()

    def draw(self, size=None, background_threshold=0.01, background_class_id=0, colors=None, return_foreground_mask=False):
        """
        Render the segmentation map as an RGB image.

        Parameters
        ----------
        size : None or float or iterable of two ints or iterable of two floats, optional(default=None)
            Size of the rendered RGB image as (height, width).
            See `imresize_single_image()` for details.
            If set to None, no resizing is performed and the size of the segmentation map array is
            used.

        background_threshold : float, optional(default=0.01)
            At each pixel, each class-heatmap has a value between 0.0 and 1.0. If none of the
            class-heatmaps has a value above this threshold, the method uses the background class
            id instead.

        background_class_id : int, optional(default=0)
            Class id to fall back to if no class-heatmap passes the threshold at a spatial
            location.

        colors : None or list of tuple of int, optional(default=None)
            Colors to use. One for each class to draw. If None, then default colors will be used.

        return_foreground_mask : bool, optional(default=False)
            Whether to return a mask of the same size as the drawn segmentation map, containing
            True at any spatial location that is not the background class and False everywhere
            else.

        Returns
        -------
        segmap_drawn : (H,W,3) ndarray(uint8)
            Rendered segmentation map.
        foreground_mask : (H,W) ndarray(bool)
            Mask indicating the locations of foreground classes. Only returned if
            return_foreground_mask is True.

        """
        arr = self.get_arr_int(background_threshold=background_threshold, background_class_id=background_class_id)
        nb_classes = self.nb_classes
        segmap_drawn = np.zeros((arr.shape[0], arr.shape[1], 3), dtype=np.uint8)
        if colors is None:
            colors = SegmentationMapOnImage.DEFAULT_SEGMENT_COLORS
        assert nb_classes <= len(colors), "Can't draw all %d classes as it would exceed the maximum number of %d available colors." % (nb_classes, len(colors),)

        ids_in_map = np.unique(arr)
        for c, color in zip(sm.xrange(1+nb_classes), colors):
            if c in ids_in_map:
                class_mask = (arr == c)
                segmap_drawn[class_mask] = color

        if return_foreground_mask:
            foreground_mask = (arr != background_class_id)
        else:
            foreground_mask = None

        if size is not None:
            segmap_drawn = imresize_single_image(segmap_drawn, size, interpolation="nearest")
            if foreground_mask is not None:
                foreground_mask = imresize_single_image(foreground_mask.astype(np.uint8), size, interpolation="nearest") > 0

        if foreground_mask is not None:
            return segmap_drawn, foreground_mask
        return segmap_drawn

    def draw_on_image(self, image, alpha=0.5, resize="segmentation_map", background_threshold=0.01, background_class_id=0, colors=None, draw_background=False):
        """
        Draw the segmentation map as an overlay over an image.

        Parameters
        ----------
        image : (H,W,3) ndarray(uint8)
            Image onto which to draw the segmentation map.

        alpha : float, optional(default=0.75)
            Alpha/opacity value to use for the mixing of image and segmentation map.
            Higher values mean that the segmentation map will be more visible and the image less
            visible.

        resize : "segmentation_map" or "image", optional(default="segmentation_map")
            In case of size differences between the image and segmentation map, either the image or
            the segmentation map can be resized. This parameter controls which of the two will be
            resized to the other's size.

        background_threshold : float, optional(default=0.01)
            At each pixel, each class-heatmap has a value between 0.0 and 1.0. If none of the
            class-heatmaps has a value above this threshold, the method uses the background class
            id instead.

        background_class_id : int, optional(default=0)
            Class id to fall back to if no class-heatmap passes the threshold at a spatial
            location.

        colors : None or list of tuple of int, optional(default=None)
            Colors to use. One for each class to draw. If None, then default colors will be used.

        draw_background : bool, optional(default=False)
            If True, the background will be drawn like any other class.
            If False, the background will not be drawn, i.e. the respective background pixels
            will be identical with the image's RGB color at the corresponding spatial location
            and no color overlay will be applied.

        Returns
        -------
        mix : (H,W,3) ndarray(uint8)
            Rendered overlays.

        """
        # assert RGB image
        assert image.ndim == 3
        assert image.shape[2] == 3
        assert image.dtype.type == np.uint8

        assert 0 - 1e-8 <= alpha <= 1.0 + 1e-8
        assert resize in ["segmentation_map", "image"]

        if resize == "image":
            image = imresize_single_image(image, self.arr.shape[0:2], interpolation="cubic")

        segmap_drawn, foreground_mask = self.draw(
            background_threshold=background_threshold,
            background_class_id=background_class_id,
            size=image.shape[0:2] if resize == "segmentation_map" else None,
            colors=colors,
            return_foreground_mask=True
        )

        if draw_background:
            mix = np.clip(
                (1-alpha) * image + alpha * segmap_drawn,
                0,
                255
            ).astype(np.uint8)
        else:
            foreground_mask = foreground_mask[..., np.newaxis]
            mix = np.zeros_like(image)
            mix += (~foreground_mask).astype(np.uint8) * image
            mix += foreground_mask.astype(np.uint8) * np.clip(
                (1-alpha) * image + alpha * segmap_drawn,
                0,
                255
            ).astype(np.uint8)
        return mix

    def pad(self, top=0, right=0, bottom=0, left=0, mode="constant", cval=0.0):
        """
        Pad the segmentation map on its top/right/bottom/left side.

        Parameters
        ----------
        top : int, optional(default=0)
            Amount of pixels to add at the top side of the segmentation map. Must be 0 or
            greater.

        right : int, optional(default=0)
            Amount of pixels to add at the right side of the segmentation map. Must be 0 or
            greater.

        bottom : int, optional(default=0)
            Amount of pixels to add at the bottom side of the segmentation map. Must be 0 or
            greater.

        left : int, optional(default=0)
            Amount of pixels to add at the left side of the segmentation map. Must be 0 or
            greater.

        mode : string, optional(default="constant")
            Padding mode to use. See `numpy.pad()` for details.

        cval : number, optional(default=0.0)
            Value to use for padding if mode="constant". See `numpy.pad()` for details.

        Returns
        -------
        result : SegmentationMapOnImage
            Padded segmentation map of height H'=H+top+bottom and width W'=W+left+right.

        """
        arr_padded = pad(self.arr, top=top, right=right, bottom=bottom, left=left, mode=mode, cval=cval)
        return SegmentationMapOnImage(arr_padded, shape=self.shape)

    def pad_to_aspect_ratio(self, aspect_ratio, mode="constant", cval=0.0, return_pad_amounts=False):
        """
        Pad the segmentation map on its sides so that its matches a target aspect ratio.

        Depending on which dimension is smaller (height or width), only the corresponding
        sides (left/right or top/bottom) will be padded. In each case, both of the sides will
        be padded equally.

        Parameters
        ----------
        aspect_ratio : float
            Target aspect ratio, given as width/height. E.g. 2.0 denotes the image having twice
            as much width as height.

        mode : string, optional(default="constant")
            Padding mode to use. See `numpy.pad()` for details.

        cval : number, optional(default=0.0)
            Value to use for padding if mode="constant". See `numpy.pad()` for details.

        return_pad_amounts : bool, optional(default=False)
            If False, then only the padded image will be returned. If True, a tuple with two
            entries will be returned, where the first entry is the padded image and the second
            entry are the amounts by which each image side was padded. These amounts are again a
            tuple of the form (top, right, bottom, left), with each value being an integer.

        Returns
        -------
        result : tuple
            First tuple entry: Padded segmentation map as SegmentationMapOnImage object.
            Second tuple entry: Amounts by which the segmentation map was padded on each side,
            given as a tuple (top, right, bottom, left).
            If return_pad_amounts is False, then only the segmentation map object is returned.

        """
        arr_padded, pad_amounts = pad_to_aspect_ratio(self.arr, aspect_ratio=aspect_ratio, mode=mode, cval=cval, return_pad_amounts=True)
        segmap = SegmentationMapOnImage(arr_padded, shape=self.shape)
        if return_pad_amounts:
            return segmap, pad_amounts
        else:
            return segmap

    def scale(self, sizes, interpolation="cubic"):
        """
        Rescale the segmentation map array to the provided size given the provided interpolation.

        Parameters
        ----------
        sizes : float or iterable of two ints or iterable of two floats
            New size of the array in (height, width). See `imresize_single_image()` for details.

        interpolation : None or string or int, optional(default="cubic")
            The interpolation to use during resize. See `imresize_single_image()` for details.
            Note: The segmentation map is internally stored as multiple float-based heatmaps,
            making smooth interpolations potentially more reasonable than nearest neighbour
            interpolation.

        Returns
        -------
        result : SegmentationMapOnImage
            Rescaled segmentation map object.

        """
        arr_rescaled = imresize_single_image(self.arr, sizes, interpolation=interpolation)

        # cubic interpolation can lead to values outside of [0.0, 1.0],
        # see https://github.com/opencv/opencv/issues/7195
        # TODO area interpolation too?
        arr_rescaled = np.clip(arr_rescaled, 0.0, 1.0)

        return SegmentationMapOnImage(arr_rescaled, shape=self.shape)

    def to_heatmaps(self, only_nonempty=False, not_none_if_no_nonempty=False):
        """
        Convert segmentation map to heatmaps object.

        Each segmentation map class will be represented as a single heatmap channel.

        Parameters
        ----------
        only_nonempty : bool, optional(default=False)
            If True, then only heatmaps for classes that appear in the segmentation map will be
            generated. Additionally, a list of these class ids will be returned.

        not_none_if_no_nonempty : bool, optional(default=False)
            If `only_nonempty` is True and for a segmentation map no channel was non-empty,
            this function usually returns None as the heatmaps object. If however this parameter
            is set to True, a heatmaps object with one channel (representing class 0)
            will be returned as a fallback in these cases.

        Returns
        -------
        result : HeatmapsOnImage or None
            Segmentation map as heatmaps.
            If `only_nonempty` was set to True and no class appeared in the segmentation map,
            then this is None.
        class_indices : list of int
            Class ids (0 to C-1) of the classes that were actually added to the heatmaps.
            Only returned if `only_nonempty` was set to True.

        """
        if not only_nonempty:
            return HeatmapsOnImage.from_0to1(self.arr, self.shape, min_value=0.0, max_value=1.0)
        else:
            nonempty_mask = np.sum(self.arr, axis=(0, 1)) > 0 + 1e-4
            if np.sum(nonempty_mask) == 0:
                if not_none_if_no_nonempty:
                    nonempty_mask[0] = True
                else:
                    return None, []

            class_indices = np.arange(self.arr.shape[2])[nonempty_mask]
            channels = self.arr[..., class_indices]
            return HeatmapsOnImage(channels, self.shape, min_value=0.0, max_value=1.0), class_indices

    @staticmethod
    def from_heatmaps(heatmaps, class_indices=None, nb_classes=None):
        """
        Convert heatmaps to segmentation map.

        Assumes that each class is represented as a single heatmap channel.

        Parameters
        ----------
        heatmaps : HeatmapsOnImage
            Heatmaps to convert.

        class_indices : None or list of int, optional(default=None)
            List of class indices represented by each heatmap channel. See also the
            secondary output of `to_heatmap()`. If this is provided, it must have the same
            length as the number of heatmap channels.

        nb_classes : None or int, optional(default=None)
            Number of classes. Must be provided if class_indices is set.

        Returns
        -------
        result : SegmentationMapOnImage
            Segmentation map derived from heatmaps.

        """
        if class_indices is None:
            return SegmentationMapOnImage(heatmaps.arr_0to1, shape=heatmaps.shape)
        else:
            assert nb_classes is not None
            assert min(class_indices) >= 0
            assert max(class_indices) < nb_classes
            assert len(class_indices) == heatmaps.arr_0to1.shape[2]
            arr_0to1 = heatmaps.arr_0to1
            arr_0to1_full = np.zeros((arr_0to1.shape[0], arr_0to1.shape[1], nb_classes), dtype=np.float32)
            #empty_channel = np.zeros((arr_0to1.shape[0], arr_0to1.shape[1]), dtype=np.float32)
            class_indices_set = set(class_indices)
            heatmap_channel = 0
            for c in sm.xrange(nb_classes):
                if c in class_indices_set:
                    arr_0to1_full[:, :, c] = arr_0to1[:, :, heatmap_channel]
                    heatmap_channel += 1
            return SegmentationMapOnImage(arr_0to1_full, shape=heatmaps.shape)

    def copy(self):
        """
        Create a shallow copy of the segmentation map object.

        Returns
        -------
        out : SegmentationMapOnImage
            Shallow copy.

        """
        return self.deepcopy()

    def deepcopy(self):
        """
        Create a deep copy of the segmentation map object.

        Returns
        -------
        out : SegmentationMapOnImage
            Deep copy.

        """
        segmap = SegmentationMapOnImage(self.arr, shape=self.shape, nb_classes=self.nb_classes)
        segmap.input_was = self.input_was
        return segmap


############################
# Background augmentation
############################

class Batch(object):
    """
    Class encapsulating a batch before and after augmentation.

    Parameters
    ----------
    images : None or (N,H,W,C) ndarray or (N,H,W) ndarray or list of (H,W,C) ndarray or list of (H,W) ndarray
        The images to
        augment.

    keypoints : None or list of KeypointOnImage
        The keypoints to
        augment.

    data : anything
        Additional data that is saved in the batch and may be read out
        after augmentation. This could e.g. contain filepaths to each image
        in `images`. As this object is usually used for background
        augmentation with multiple processes, the augmented Batch objects might
        not be returned in the original order, making this information useful.

    """
    def __init__(self, images=None, images_gt=None, mask_gt=None, keypoints=None, data=None):
        self.images = images
        self.images_aug = None
        self.images_gt = images_gt
        self.images_gt_aug = None
        self.mask_gt = mask_gt
        self.mask_gt_aug = None
        self.keypoints = keypoints
        self.keypoints_aug = None
        self.data = data

class BatchLoader(object):
    """
    Class to load batches in the background.

    Loaded batches can be accesses using `BatchLoader.queue`.

    Parameters
    ----------
    load_batch_func : callable
        Function that yields Batch objects (i.e. expected to be a generator).
        Background loading automatically stops when the last batch was yielded.

    queue_size : int, optional(default=50)
        Maximum number of batches to store in the queue. May be set higher
        for small images and/or small batches.

    nb_workers : int, optional(default=1)
        Number of workers to run in the background.

    threaded : bool, optional(default=True)
        Whether to run the background processes using threads (true) or
        full processes (false).

    """

    def __init__(self, load_batch_func, queue_size=50, nb_workers=1, threaded=True):
        do_assert(queue_size > 0)
        do_assert(nb_workers >= 1)
        self.queue = multiprocessing.Queue(queue_size)
        self.join_signal = multiprocessing.Event()
        self.finished_signals = []
        self.workers = []
        self.threaded = threaded
        seeds = current_random_state().randint(0, 10**6, size=(nb_workers,))
        for i in range(nb_workers):
            finished_signal = multiprocessing.Event()
            self.finished_signals.append(finished_signal)
            if threaded:
                worker = threading.Thread(target=self._load_batches, args=(load_batch_func, self.queue, finished_signal, self.join_signal, None))
            else:
                worker = multiprocessing.Process(target=self._load_batches, args=(load_batch_func, self.queue, finished_signal, self.join_signal, seeds[i]))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def all_finished(self):
        """
        Determine whether the workers have finished the loading process.

        Returns
        -------
        out : bool
            True if all workers have finished. Else False.

        """
        return all([event.is_set() for event in self.finished_signals])

    def _load_batches(self, load_batch_func, queue, finished_signal, join_signal, seedval):
        if seedval is not None:
            random.seed(seedval)
            np.random.seed(seedval)
            seed(seedval)

        try:
            for batch in load_batch_func():
                do_assert(isinstance(batch, Batch), "Expected batch returned by lambda function to be of class imgaug.Batch, got %s." % (type(batch),))
                batch_pickled = pickle.dumps(batch, protocol=-1)
                while not join_signal.is_set():
                    try:
                        queue.put(batch_pickled, timeout=0.001)
                        break
                    except QueueFull:
                        pass
                if join_signal.is_set():
                    break
        except Exception as exc:
            traceback.print_exc()
        finally:
            finished_signal.set()

    def terminate(self):
        """
        Stop all workers.

        """
        self.join_signal.set()
        # give minimal time to put generated batches in queue and gracefully shut down
        time.sleep(0.002)

        # clean the queue, this reportedly prevents hanging threads
        while True:
            try:
                self.queue.get(timeout=0.005)
            except QueueEmpty:
                break

        if self.threaded:
            for worker in self.workers:
                worker.join()
            # we don't have to set the finished_signals here, because threads always finish
            # gracefully
        else:
            for worker in self.workers:
                worker.terminate()
                worker.join()

            # wait here a tiny bit to really make sure that everything is killed before setting
            # the finished_signals. calling set() and is_set() (via a subprocess) on them at the
            # same time apparently results in a deadlock (at least in python 2).
            #time.sleep(0.02)
            for finished_signal in self.finished_signals:
                finished_signal.set()

        self.queue.close()

class BackgroundAugmenter(object):
    """
    Class to augment batches in the background (while training on the GPU).

    This is a wrapper around the multiprocessing module.

    Parameters
    ----------
    batch_loader : BatchLoader
        BatchLoader object to load data in the
        background.

    augseq : Augmenter
        An augmenter to apply to all loaded images.
        This may be e.g. a Sequential to apply multiple augmenters.

    queue_size : int
        Size of the queue that is used to temporarily save the augmentation
        results. Larger values offer the background processes more room
        to save results when the main process doesn't load much, i.e. they
        can lead to smoother and faster training. For large images, high
        values can block a lot of RAM though.

    nb_workers : "auto" or int
        Number of background workers to spawn. If auto, it will be set
        to C-1, where C is the number of CPU cores.

    """
    def __init__(self, batch_loader, augseq, augseq_X=None, augseq_gt=None, queue_size=50, nb_workers="auto"):
        do_assert(queue_size > 0)
        self.augseq = augseq
        self.augseq_X = augseq_X
        self.augseq_gt = augseq_gt
        self.source_finished_signals = batch_loader.finished_signals
        self.queue_source = batch_loader.queue
        self.queue_result = multiprocessing.Queue(queue_size)

        if nb_workers == "auto":
            try:
                nb_workers = multiprocessing.cpu_count()
            except (ImportError, NotImplementedError):
                nb_workers = 1
            # try to reserve at least one core for the main process
            nb_workers = max(1, nb_workers - 1)
        else:
            do_assert(nb_workers >= 1)
        #print("Starting %d background processes" % (nb_workers,))

        self.nb_workers = nb_workers
        self.workers = []
        self.nb_workers_finished = 0

        self.augment_images = True
        self.augment_images_gt = True
        self.augment_keypoints = True

        seeds = current_random_state().randint(0, 10**6, size=(nb_workers,))
        for i in range(nb_workers):
            worker = multiprocessing.Process(target=self._augment_images_worker, args=(augseq, augseq_X, augseq_gt, self.queue_source, self.queue_result, self.source_finished_signals, seeds[i]))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def get_batch(self):
        """
        Returns a batch from the queue of augmented batches.

        If workers are still running and there are no batches in the queue,
        it will automatically wait for the next batch.

        Returns
        -------
        out : None or ia.Batch
            One batch or None if all workers have finished.

        """
        batch_str = self.queue_result.get()
        batch = pickle.loads(batch_str)
        if batch is not None:
            return batch
        else:
            self.nb_workers_finished += 1
            if self.nb_workers_finished == self.nb_workers:
                return None
            else:
                return self.get_batch()

    def _augment_images_worker(self, augseq, augseq_X, augseq_gt, queue_source, queue_result, source_finished_signals, seedval):
        """
        Worker function that endlessly queries the source queue (input
        batches), augments batches in it and sends the result to the output
        queue.

        """
        np.random.seed(seedval)
        random.seed(seedval)
        augseq.reseed(seedval)
        if augseq_X:
            augseq_X.reseed(seedval)
        if augseq_gt:
            augseq_gt.reseed(seedval)
        seed(seedval)

        while True:
            # wait for a new batch in the source queue and load it
            try:
                batch_str = queue_source.get(timeout=0.1)
                batch = pickle.loads(batch_str)
                # augment the batch
                batch_augment_images = batch.images is not None and self.augment_images
                batch_augment_images_gt = batch.images_gt is not None and self.augment_images_gt
                batch_augment_keypoints = batch.keypoints is not None and self.augment_keypoints

                if batch_augment_images and batch_augment_keypoints:
                    augseq_det = augseq.to_deterministic() if not augseq.deterministic else augseq
                    batch.images_aug = augseq_det.augment_images(batch.images)
                    batch.keypoints_aug = augseq_det.augment_keypoints(batch.keypoints)
                elif batch_augment_images and batch_augment_images_gt:
                    augseq_det = augseq.to_deterministic() if not augseq.deterministic else augseq
                    batch.images_aug = augseq_det.augment_images(batch.images)
                    batch.images_gt_aug = augseq_det.augment_images(batch.images_gt)
                    batch.mask_gt_aug = augseq_det.augment_images(batch.mask_gt)

                    if augseq_X:
                        batch.images_aug = augseq_X.augment_images(batch.images_aug)

                    if augseq_gt:
                        augseq_gt_det = augseq_gt.to_deterministic() if not augseq_gt.deterministic else augseq_gt
                        batch.images_gt_aug = augseq_gt_det.augment_images(batch.images_gt_aug)
                        batch.mask_gt_aug = augseq_gt_det.augment_images(batch.mask_gt_aug)

                elif batch_augment_images:
                    batch.images_aug = augseq.augment_images(batch.images)
                elif batch_augment_keypoints:
                    batch.keypoints_aug = augseq.augment_keypoints(batch.keypoints)

                # send augmented batch to output queue
                batch_str = pickle.dumps(batch, protocol=-1)
                queue_result.put(batch_str)
            except QueueEmpty:
                if all([signal.is_set() for signal in source_finished_signals]):
                    queue_result.put(pickle.dumps(None, protocol=-1))
                    return

    def terminate(self):
        """
        Terminates all background processes immediately.
        This will also free their RAM.

        """
        for worker in self.workers:
            worker.terminate()

        self.queue_result.close()
