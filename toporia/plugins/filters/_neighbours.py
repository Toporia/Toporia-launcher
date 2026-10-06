# plugins/filters/_neighbours.py — the weighted-neighbour matrix of the density and sensitivity filters, in any dimension.
#
#     H[e, f] = max(0, rmin − distance(e, f))      (distances in elements)
#
# Built for a field of any shape, elements numbered in C order.  The 2-D
# filters keep their original loops (column-major, as in top88), so 2-D
# results do not change by a single bit; this is used for 3-D problems.

import itertools

import numpy as np
from scipy.sparse import coo_matrix


def neighbour_matrix(shape, rmin):
    """(H, Hs): the sparse weights and their row sums, for elements in C order over `shape`."""
    reach = int(np.ceil(rmin) - 1)
    index = np.arange(int(np.prod(shape))).reshape(shape)
    rows, cols, vals = [], [], []
    for offset in itertools.product(range(-reach, reach + 1), repeat=len(shape)):
        weight = rmin - np.sqrt(sum(o * o for o in offset))
        if weight <= 0.0:
            continue
        # The elements whose neighbour at `offset` lies inside the domain.
        source = tuple(slice(max(0, -o), n - max(0, o)) for o, n in zip(offset, shape))
        target = tuple(slice(max(0, o), n - max(0, -o)) for o, n in zip(offset, shape))
        rows.append(index[source].ravel())
        cols.append(index[target].ravel())
        vals.append(np.full(rows[-1].size, weight))
    n = index.size
    H = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    return H, np.asarray(H.sum(axis=1)).ravel()
