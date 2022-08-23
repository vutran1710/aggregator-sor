from collections.abc import Callable
from typing import Dict
from typing import List
from typing import Optional

from .models import Dex
from .models import Edge
from .models import Pool
from .models import SwapEdge
from .models import Token
from .preprocess import TokenPairsPools


def find_edges(
    dexes: List[Dex],
    token_in: Token,
    token_out: Token,
    pool_list: List[Pool],
    pool_map: Dict[str, Pool],
    token_pairs_pools: TokenPairsPools,
    max_hop=4,
) -> List[Edge]:
    if token_in not in token_pairs_pools:
        return []

    if token_out not in token_pairs_pools:
        return []

    if token_in == token_out:
        return []

    if not dexes:
        return []

    if not pool_list:
        return []

    if not pool_map:
        return []

    result = []

    def trace(token: Token, queue=None):
        nonlocal token_out, max_hop

        if not queue:
            queue = []

        queue.append(token)

        if len(queue) > max_hop:
            return

        if token == token_out:
            result.append(queue.copy())
            return

        nodes = list(token_pairs_pools[token].keys())

        for node in nodes:
            if len(queue) >= 2 and node == queue[-2]:
                continue

            trace(node, queue=queue)

            while queue[-1] != token:
                queue.pop()

    trace(token_in)
    return result


Splits = List[float]
BatchSplitCallback = Callable[[Splits], None]


def batch_split(
    batch_size: float,
    batch_count: int,
    optimal_lv=5,
    callback: Optional[BatchSplitCallback] = None,
) -> Optional[List[Splits]]:
    result: List[Splits] = []

    def split(
        current_batch_size: float,
        batch_idx=0,
        queue: Optional[Splits] = None,
    ):
        nonlocal batch_count, optimal_lv, result, callback

        if not queue:
            queue = []

        if len(queue) == batch_count - 1:
            queue.append(current_batch_size)
            splits = queue.copy()

            if callback:
                callback(splits)
            else:
                result.append(splits)

            queue.pop()
            return

        for i in range(optimal_lv + 1):
            split_head = round(current_batch_size * i / optimal_lv, 5)
            split_remain = round(current_batch_size - split_head, 5)
            queue.append(split_head)
            # FIXME: edge-cases
            # 1/ when no more amount to distribute
            # 2/ duplicated distributions
            split(split_remain, batch_idx=batch_idx + 1, queue=queue)
            queue.pop()

    split(batch_size)

    return result if not callback else None


def swap_edge_amount_out(swap_edge: SwapEdge, amount_in: float, optimal_lv=5):
    pools = swap_edge.sort_pools(amount_in)
    max_out = 0
    optimal_splits = []
    pool_order = [pool.name for pool in pools]

    def test_amount(splits: Splits):
        nonlocal max_out, optimal_splits, pool_order
        result = 0

        for idx, part in enumerate(splits):
            result += pools[idx].swap(
                swap_edge.token_in,
                part,
                swap_edge.token_out,
            )

        print(result, splits)
        if result > max_out:
            max_out = result
            optimal_splits = [s / amount_in * 100 for s in splits]

    batch_split(
        amount_in,
        len(pools),
        optimal_lv=optimal_lv,
        callback=test_amount,
    )

    return max_out, optimal_splits, pool_order
