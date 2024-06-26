from itertools import product
from sys import float_info
from typing import Tuple

import numpy as np
import pandas as pd

from src.resources import PATH_KNW_GRID

_latitudes = pd.Series([
    49.000, 49.023, 49.046, 49.069, 49.092, 49.115, 49.138, 49.161,
    49.184, 49.207, 49.230, 49.253, 49.276, 49.299, 49.322, 49.345,
    49.368, 49.391, 49.414, 49.437, 49.460, 49.483, 49.506, 49.529,
    49.552, 49.575, 49.598, 49.621, 49.644, 49.667, 49.690, 49.713,
    49.736, 49.759, 49.782, 49.805, 49.828, 49.851, 49.874, 49.897,
    49.920, 49.943, 49.966, 49.989, 50.012, 50.035, 50.058, 50.081,
    50.104, 50.127, 50.150, 50.173, 50.196, 50.219, 50.242, 50.265,
    50.288, 50.311, 50.334, 50.357, 50.380, 50.403, 50.426, 50.449,
    50.472, 50.495, 50.518, 50.541, 50.564, 50.587, 50.610, 50.633,
    50.656, 50.679, 50.702, 50.725, 50.748, 50.771, 50.794, 50.817,
    50.840, 50.863, 50.886, 50.909, 50.932, 50.955, 50.978, 51.001,
    51.024, 51.047, 51.070, 51.093, 51.116, 51.139, 51.162, 51.185,
    51.208, 51.231, 51.254, 51.277, 51.300, 51.323, 51.346, 51.369,
    51.392, 51.415, 51.438, 51.461, 51.484, 51.507, 51.530, 51.553,
    51.576, 51.599, 51.622, 51.645, 51.668, 51.691, 51.714, 51.737,
    51.760, 51.783, 51.806, 51.829, 51.852, 51.875, 51.898, 51.921,
    51.944, 51.967, 51.990, 52.013, 52.036, 52.059, 52.082, 52.105,
    52.128, 52.151, 52.174, 52.197, 52.220, 52.243, 52.266, 52.289,
    52.312, 52.335, 52.358, 52.381, 52.404, 52.427, 52.450, 52.473,
    52.496, 52.519, 52.542, 52.565, 52.588, 52.611, 52.634, 52.657,
    52.680, 52.703, 52.726, 52.749, 52.772, 52.795, 52.818, 52.841,
    52.864, 52.887, 52.910, 52.933, 52.956, 52.979, 53.002, 53.025,
    53.048, 53.071, 53.094, 53.117, 53.140, 53.163, 53.186, 53.209,
    53.232, 53.255, 53.278, 53.301, 53.324, 53.347, 53.370, 53.393,
    53.416, 53.439, 53.462, 53.485, 53.508, 53.531, 53.554, 53.577,
    53.600, 53.623, 53.646, 53.669, 53.692, 53.715, 53.738, 53.761,
    53.784, 53.807, 53.830, 53.853, 53.876, 53.899, 53.922, 53.945,
    53.968, 53.991, 54.014, 54.037, 54.060, 54.083, 54.106, 54.129,
    54.152, 54.175, 54.198, 54.221, 54.244, 54.267, 54.290, 54.313,
    54.336, 54.359, 54.382, 54.405, 54.428, 54.451, 54.474, 54.497,
    54.520, 54.543, 54.566, 54.589, 54.612, 54.635, 54.658, 54.681,
    54.704, 54.727, 54.750, 54.773, 54.796, 54.819, 54.842, 54.865,
    54.888, 54.911, 54.934, 54.957, 54.980, 55.003, 55.026, 55.049,
    55.072, 55.095, 55.118, 55.141, 55.164, 55.187, 55.210, 55.233,
    55.256, 55.279, 55.302, 55.325, 55.348, 55.371, 55.394, 55.417,
    55.440, 55.463, 55.486, 55.509, 55.532, 55.555, 55.578, 55.601,
    55.624, 55.647, 55.670, 55.693, 55.716, 55.739, 55.762, 55.785,
    55.808, 55.831, 55.854, 55.877])
_longitudes = pd.Series([
    0.000, 0.037, 0.074, 0.111, 0.148, 0.185, 0.222, 0.259, 0.296,
    0.333, 0.370, 0.407, 0.444, 0.481, 0.518, 0.555, 0.592, 0.629,
    0.666, 0.703, 0.740, 0.777, 0.814, 0.851, 0.888, 0.925, 0.962,
    0.999, 1.036, 1.073, 1.110, 1.147, 1.184, 1.221, 1.258, 1.295,
    1.332, 1.369, 1.406, 1.443, 1.480, 1.517, 1.554, 1.591, 1.628,
    1.665, 1.702, 1.739, 1.776, 1.813, 1.850, 1.887, 1.924, 1.961,
    1.998, 2.035, 2.072, 2.109, 2.146, 2.183, 2.220, 2.257, 2.294,
    2.331, 2.368, 2.405, 2.442, 2.479, 2.516, 2.553, 2.590, 2.627,
    2.664, 2.701, 2.738, 2.775, 2.812, 2.849, 2.886, 2.923, 2.960,
    2.997, 3.034, 3.071, 3.108, 3.145, 3.182, 3.219, 3.256, 3.293,
    3.330, 3.367, 3.404, 3.441, 3.478, 3.515, 3.552, 3.589, 3.626,
    3.663, 3.700, 3.737, 3.774, 3.811, 3.848, 3.885, 3.922, 3.959,
    3.996, 4.033, 4.070, 4.107, 4.144, 4.181, 4.218, 4.255, 4.292,
    4.329, 4.366, 4.403, 4.440, 4.477, 4.514, 4.551, 4.588, 4.625,
    4.662, 4.699, 4.736, 4.773, 4.810, 4.847, 4.884, 4.921, 4.958,
    4.995, 5.032, 5.069, 5.106, 5.143, 5.180, 5.217, 5.254, 5.291,
    5.328, 5.365, 5.402, 5.439, 5.476, 5.513, 5.550, 5.587, 5.624,
    5.661, 5.698, 5.735, 5.772, 5.809, 5.846, 5.883, 5.920, 5.957,
    5.994, 6.031, 6.068, 6.105, 6.142, 6.179, 6.216, 6.253, 6.290,
    6.327, 6.364, 6.401, 6.438, 6.475, 6.512, 6.549, 6.586, 6.623,
    6.660, 6.697, 6.734, 6.771, 6.808, 6.845, 6.882, 6.919, 6.956,
    6.993, 7.030, 7.067, 7.104, 7.141, 7.178, 7.215, 7.252, 7.289,
    7.326, 7.363, 7.400, 7.437, 7.474, 7.511, 7.548, 7.585, 7.622,
    7.659, 7.696, 7.733, 7.770, 7.807, 7.844, 7.881, 7.918, 7.955,
    7.992, 8.029, 8.066, 8.103, 8.140, 8.177, 8.214, 8.251, 8.288,
    8.325, 8.362, 8.399, 8.436, 8.473, 8.510, 8.547, 8.584, 8.621,
    8.658, 8.695, 8.732, 8.769, 8.806, 8.843, 8.880, 8.917, 8.954,
    8.991, 9.028, 9.065, 9.102, 9.139, 9.176, 9.213, 9.250, 9.287,
    9.324, 9.361, 9.398, 9.435, 9.472, 9.509, 9.546, 9.583, 9.620,
    9.657, 9.694, 9.731, 9.768, 9.805, 9.842, 9.879, 9.916, 9.953,
    9.990, 10.027, 10.064, 10.101, 10.138, 10.175, 10.212, 10.249,
    10.286, 10.323, 10.360, 10.397, 10.434, 10.471, 10.508, 10.545,
    10.582, 10.619, 10.656, 10.693, 10.730, 10.767, 10.804, 10.841,
    10.878, 10.915, 10.952, 10.989, 11.026, 11.063
])

indices = np.array(list(np.ndindex((len(_latitudes), len(_longitudes)))))
GridPoints = pd.DataFrame(list(product(_latitudes, _longitudes)),
                          columns=["latitude", "longitude"],
                          index=((indices[:, 0] + 1) * 1000) + (indices[:, 1] + 1)
                          )


def load_knw_grid(
        path: str = PATH_KNW_GRID
) -> pd.DataFrame:
    return pd.read_csv(path, comment='#', sep='\s+')


def get_gridpoint(lat: float, lon: float, _grid: pd.DataFrame):
    """
    Calculating the gridpoint closest to the lat lon
    Using this to query the weather_forecast database
    """
    _grid["delta_lat"] = _grid["latitude"] - lat
    _grid["delta_lon"] = _grid["longitude"] - lon
    _grid["distance"] = _grid["delta_lat"] ** 2 + _grid["delta_lon"] ** 2
    min_idx = _grid["distance"].idxmin()
    return min_idx


# TODO not too sure if these are needed
def square_index_closest_to_plant_actuals(
        df: pd.DataFrame,
        lat: float,
        lon: float
) -> Tuple[int, int]:
    col, row = _square_index_closest(df=df, lat=lat, lon=lon)
    return col + 1, row + 1


def _square_index_closest(df, lat, lon) -> Tuple[int, int]:
    df_ndarray = df.values

    lats = []
    lons = []

    row = -1
    col = -1
    dist_min = float_info.max

    distance = np.ndarray(shape=df_ndarray.shape, dtype=float)
    dists = []

    for i in range(len(df_ndarray[0])):
        for j in range(len(df_ndarray[1])):

            latlon = str(df_ndarray[i, j]).split('/')
            _lon = float(latlon[0])
            _lat = float(latlon[1])
            lats.append(_lat)
            lons.append(_lon)

            # in order to know which is the closest we don't need to know the actual distance,
            # the euclidian distance squared will do
            ssq = pow(lat - _lat, 2) + pow(lon - _lon, 2)
            distance[i, j] = ssq
            dists.append(distance[i, j])
            if distance[i, j] < dist_min:
                dist_min = distance[i, j]
                row = i
                col = j

    print(
        f'lon/lat: {lon}/{lat}.'
        f' Closest square, lon/lat: {df_ndarray[row, col]}. ssq: {dist_min}'
    )

    return col, row
