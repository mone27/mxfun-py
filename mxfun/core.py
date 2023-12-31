# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_core.ipynb.

# %% auto 0
__all__ = ['download_file', 'download_files', 'file_bbox', 'write_bbox_tileindex_dir', 'iter_row_df', 'str_here']

# %% ../nbs/00_core.ipynb 5
from tqdm.auto import tqdm
# import request
from pathlib import Path
from humanize import naturalsize
import asyncio
from fastcore.utils import *

import aiohttp
import aiofiles

# %% ../nbs/00_core.ipynb 6
@patch
def add_suffix(path: Path, suffix): return path.parent / (path.name + suffix)

# %% ../nbs/00_core.ipynb 7
async def download_file(url,
                        out_name,
                        session,
                        semaphore,
                        master_bar=None,
                        chunk_size = 1024,
                        overwrite = False,
                        wait = 10,
                        retry = 0,
                        max_redirects = 1,
                        max_retry = 1,
                        max_wait = 10 * 60
                       ):
    if out_name.exists() and not overwrite:
        print(f"Skipping: {url}")
        if master_bar is not None: master_bar.update()
        return
    try:
        # limit number of concurret requests
        async with semaphore:
            async with session.get(url, max_redirects = max_redirects) as resp:
                tot_size = resp.headers['Content-Length']
                with tqdm(total = int(tot_size), unit='B', unit_scale=True, unit_divisor=1024) as pbar:
                    print(f"Downloading: {url}", naturalsize(tot_size))
                    async with aiofiles.open(out_name.add_suffix(".part"), 'wb') as fd:
                        async for chunk in resp.content.iter_chunked(chunk_size):
                            await fd.write(chunk)
                            pbar.set_postfix(file=out_name.name[-10:], retry = retry, refresh=False)
                            pbar.update(chunk_size)
    except (aiohttp.TooManyRedirects, aiohttp.ClientPayloadError) as e:
        if retry > max_retry:
            raise ValueError(f"Too many retries, {retry}")
        print(f"Server error {out_name.name}. Retrying in {wait} s [{retry}/{max_retry}]")
        await asyncio.sleep(wait)
        try:
            pbar.clear()
        except NameError:
            pass # no progress bar created so no need to clear it
        # try again
        return await download_file(url, out_name,
                            session, semaphore, master_bar,
                            chunk_size, overwrite,
                            wait = wait + 60 if wait < max_wait else wait,
                            retry = retry + 1,
                            max_retry = max_retry,
                            max_redirects = max_redirects
                                  )
        
    try:
        if overwrite:
            out_name.unlink(missing_ok = True)
        out_name.add_suffix(".part").rename(out_name)
        print(f"Done: {out_name.stem}, {naturalsize(out_name.stat().st_size)}")
    except Exception as e:
        print(f"Failed: {out_name.stem}")
        print(e)
    if master_bar is not None: master_bar.update()

# %% ../nbs/00_core.ipynb 8
async def download_files(urls, out_names, overwrite = False, max_redirects = 5, max_retry = 10, timeout = 5 * 60, max_connections = 100):
    sem = asyncio.Semaphore(max_connections)
    with tqdm(total = len(urls)) as master_bar:
         async with aiohttp.ClientSession(timeout = aiohttp.ClientTimeout(timeout)) as session:
            await asyncio.gather(*[download_file(
                url, out, session, sem, master_bar = master_bar,
                overwrite = overwrite, max_redirects = max_redirects, max_retry = max_retry)
                                   for url, out in zip(urls, out_names)])

# %% ../nbs/00_core.ipynb 10
import geopandas as gpd
import pandas as pd
from shapely import box
from pyogrio import read_info, read_bounds
import numpy as np
from pathlib import Path
from dask.distributed import Client

# %% ../nbs/00_core.ipynb 11
def file_bbox(f: Path):
    """get (fast) bounding box of all features in vector file"""
    info = read_info(f)
    if info['features'] > 0:
        _, b = read_bounds(f)
        bound_geom = box(
                np.nanmin(b[0, :]),  # minx
                np.nanmin(b[1, :]),  # miny
                np.nanmax(b[2, :]),  # maxx
                np.nanmax(b[3, :]),  # maxy
        )
        return gpd.GeoDataFrame({'geometry': [bound_geom], 'path': f, 'file_name': f.name}, crs = info['crs'])

# %% ../nbs/00_core.ipynb 12
def write_bbox_tileindex_dir(
    dir_path: Path, # path of folder with individual files
    out_name: Path, # name of the 
    starts_with:str = "", # optional filter files names
    file_type:str = ".shp", # file extension
    relative:bool=True, # output path relative to
    dask_client:Client = None # optionally parallilize on dask
) -> gpd.GeoDataFrame: # tileindex
    """make and save a tileindex with bounding boxes of all files in a directory. Optionally run on dask"""
    files = dir_path.ls().filter(lambda f: f.suffix == file_type and f.name.startswith(starts_with))
    if dask_client is not None: bounds = dask_client.gather(dask_client.map(file_bbox, files))
    else: bounds = files.progress_map(file_bbox)
    tileindex = pd.concat(bounds)
    tileindex = tileindex.assign(path = tileindex.path.apply(lambda p: str(p.relative_to(out_name.parent))) if relative else tileindex.path.apply(str))
    tileindex.to_file(out_name)
    return tileindex

# %% ../nbs/00_core.ipynb 15
from tqdm.auto import tqdm
from fastcore.basics import patch, map_ex
from fastcore.foundation import L

# %% ../nbs/00_core.ipynb 16
@patch
def progress_map(self: L, f, *args, **kwargs): return self._new(map_ex(tqdm(self), f, *args, gen=False, **kwargs))

# %% ../nbs/00_core.ipynb 22
def iter_row_df(df): return [df.iloc[i:i+1] for i in range(len(df))]

# %% ../nbs/00_core.ipynb 24
@patch
def pipe(self: L, f, *args, **kwargs): return f(self, *args, **kwargs)

# %% ../nbs/00_core.ipynb 26
from pyprojroot import here

# %% ../nbs/00_core.ipynb 27
def str_here(x): return str(here(x))
