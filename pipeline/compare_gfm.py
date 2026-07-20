# pipeline/compare_gfm.py
"""Sample-point agreement between Sailaab RF mask and Copernicus GFM."""

import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform

from sailaab.validation import binary_metrics

OURS = "data/sailaab_RF_floodmask_2025.tif"
GFM = "data/gfm/gfm_punjab_20250827_0905.tif"  # adjust to the real filename
N = 5000
RNG = np.random.default_rng(42)


def sample_values(path, xs, ys, src_crs):
    with rasterio.open(path) as ds:
        if ds.crs != src_crs:
            xs, ys = warp_transform(src_crs, ds.crs, xs, ys)
        return np.array([v[0] for v in ds.sample(zip(xs, ys))])


def main():
    with rasterio.open(OURS) as ds:
        b = ds.bounds
        xs = RNG.uniform(b.left, b.right, N)
        ys = RNG.uniform(b.bottom, b.top, N)
        crs = ds.crs
    ours = sample_values(OURS, xs, ys, crs) > 0
    gfm = sample_values(GFM, xs, ys, crs) > 0
    print(binary_metrics(ours, gfm))


if __name__ == "__main__":
    main()
