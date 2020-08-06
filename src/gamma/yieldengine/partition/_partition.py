"""
Core implementation of :mod:`gamma.yieldengine.partition`
"""
import logging
import math
from abc import ABCMeta, abstractmethod
from typing import *

import numpy as np
import pandas as pd

from pytools.common.fit import FittableMixin

log = logging.getLogger(__name__)

__all__ = [
    "T_Number",
    "T_Value",
    "DEFAULT_MAX_PARTITIONS",
    "Partitioner",
    "RangePartitioner",
    "ContinuousRangePartitioner",
    "IntegerRangePartitioner",
    "CategoryPartitioner",
]

DEFAULT_MAX_PARTITIONS = 20

T = TypeVar("T")
T_Value = TypeVar("T_Value")
T_Number = TypeVar("T_Number", int, float)


class Partitioner(
    FittableMixin[Sequence[T_Value]], Generic[T_Value], metaclass=ABCMeta
):
    """Partition a set of values, for use in visualizations and simulations."""

    def __init__(self, max_partitions: int = None):
        if max_partitions is None:
            self._max_partitions = DEFAULT_MAX_PARTITIONS
        elif max_partitions < 2:
            raise ValueError(f"arg max_partitions={max_partitions} must be at least 2")
        else:
            self._max_partitions = max_partitions

    @property
    def max_partitions(self) -> int:
        """
        The maximum number of partitions to be generated by this partitioner.
        """
        return self._max_partitions

    @abstractmethod
    def fit(self: T, values: Sequence[T_Value], **fit_params) -> T:
        """
        Calculate the partitioning for the given values.
        :param values: the values to partition
        :return: self
        """
        pass

    @abstractmethod
    def partitions(self) -> Sequence[T_Value]:
        """
        Return central values of the partitions.

        :return: for each partition, return a central value representing the partition
        """
        pass

    @abstractmethod
    def frequencies(self) -> Sequence[int]:
        """
        Return the number of elements in each partitions.

        :return: for each partition, the number of observed values that fall within
          the partition
        """

    @property
    @abstractmethod
    def is_categorical(self) -> bool:
        """```True``` if this is partitioner fits categorical values."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass


class RangePartitioner(Partitioner[T_Number], Generic[T_Number], metaclass=ABCMeta):
    """
    Partition numerical values in successive intervals of the same length.

    The partitions are made of intervals which have all the same lengths. The
    interval length is computed based on
    :attr:`max_partitions`, :attr:`lower_bound` and :attr:`upper_bound` by
    :meth:`_step_size`.

    Each partition is an interval whose endpoints are multiple of the interval
    length. The intervals satisfy the following conditions:
    - :attr:`lower_bound` is in the first interval
    - :attr:`upper_bound` is in the last interval

    For example, if the computed interval length is 0.2, some possible
    partitions would be:
    [3.2, 3.4), [3.4, 3.6), [3.6, 3.8), [4.0, 4.2), [4.4, 4.6), [4.6, 4.8]

    Implementations must define :meth:`_step_size` and :meth:`_partition_center_offset`.

    :param max_partitions: the max number of partitions to make (default: 20);
      should be at least 2
    :param lower_bound: the lower bound of the elements in the partition
    :param upper_bound: the upper bound of the elements in the partition
    """

    def __init__(
        self,
        max_partitions: int = None,
        lower_bound: Optional[T_Number] = None,
        upper_bound: Optional[T_Number] = None,
    ) -> None:
        super().__init__(max_partitions)

        if (
            lower_bound is not None
            and upper_bound is not None
            and lower_bound >= upper_bound
        ):
            raise ValueError(
                f"arg lower_bound >= arg upper_bound: [{lower_bound}, {upper_bound})"
            )

        self._lower_bound = lower_bound
        self._upper_bound = upper_bound

        self._step = None
        self._first_partition = None
        self._last_partition = None
        self._n_partitions = None
        self._frequencies = None

    @property
    def lower_bound(self) -> T_Number:
        """
        The lower bound of the partitioning.

        ``Null`` if no explicit lower bound is set.
        """
        return self._lower_bound

    @property
    def upper_bound(self) -> T_Number:
        """
        The upper bound of the partitioning.

        ``Null`` if no explicit upper bound is set.
        """
        return self._upper_bound

    # noinspection PyMissingOrEmptyDocstring
    def fit(
        self: T,
        values: Sequence[T_Value],
        lower_bound: Optional[T_Number] = None,
        upper_bound: Optional[T_Number] = None,
        **fit_params,
    ) -> T:
        # we inherit the docstring from the super method
        # (see statement following this method declaration)

        self: RangePartitioner  # support type hinting in PyCharm

        lower_bound = self._lower_bound
        upper_bound = self._upper_bound

        if lower_bound is None:
            lower_bound = np.quantile(values, q=0.025)

        if upper_bound is None:
            upper_bound = np.quantile(values, q=0.975)
            if upper_bound < lower_bound:
                upper_bound = lower_bound
        elif upper_bound < lower_bound:
            lower_bound = upper_bound

        # calculate the step count based on the maximum number of partitions,
        # rounded to the next-largest rounded value ending in 1, 2, or 5
        self._step = step = self._step_size(lower_bound, upper_bound)

        # calculate centre values of the first and last partition;
        # both are rounded to multiples of the step size
        self._first_partition = first_partition = (
            math.floor((lower_bound + step / 2) / step) * step
        )
        self._last_partition = math.ceil((upper_bound - step / 2) / step) * step
        self._n_partitions = n_partitions = (
            int(round((self._last_partition - self._first_partition) / self._step)) + 1
        )

        def _frequencies() -> List[int]:
            # Return the number of elements in each partitions
            partition_indices = [
                int(round(value - first_partition) / step) for value in values
            ]
            frequencies = [0] * n_partitions
            for idx in partition_indices:
                if 0 <= idx < n_partitions:
                    frequencies[idx] += 1

            return frequencies

        self._frequencies = _frequencies()
        return self

    fit.__doc__ = Partitioner.fit.__doc__

    def is_fitted(self) -> bool:
        """``True`` if this partitioner is fitted, else ``False``"""
        return self._frequencies is not None

    def partitions(self) -> Sequence[T_Number]:
        """
        Return the central values of the partitions.

        :return: for each partition, a central value representing the partition
        """
        offset = self._first_partition
        step = self._step
        return [offset + (idx * step) for idx in range(self._n_partitions)]

    def frequencies(self) -> Sequence[int]:
        """
        Return the number of elements in each partitions.

        :return: for each partition, the number of observed values that fall within
          the partition
        """
        return self._frequencies

    @property
    def is_categorical(self) -> bool:
        """```False```"""
        return False

    def partition_bounds(self) -> Sequence[Tuple[T_Number, T_Number]]:
        """
        Return the endpoints of the intervals that delineate each partitions.

        :return: sequence of tuples (x, y) for every partition, where x is the
          inclusive lower bound of a partition range, and y is the exclusive upper
          bound of a partition range
        """

        center_offset_left = self._partition_center_offset
        center_offset_right = self._step - center_offset_left
        return [
            (center - center_offset_left, center + center_offset_right)
            for center in self.partitions()
        ]

    @property
    def partition_width(self) -> T_Number:
        """The width of each partition."""
        return self._step

    @staticmethod
    def _ceil_step(step: float):
        """
        Round the step size (arbitrary float) to a human-readable number like 0.5, 1, 2.

        :param step: the step size to round by
        :return: the nearest greater or equal step size in the series
                 (..., 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, ...)
        """
        if step <= 0:
            raise ValueError("arg step must be positive")

        return min(10 ** math.ceil(math.log10(step * m)) / m for m in [1, 2, 5])

    @staticmethod
    @abstractmethod
    def _step_size(lower_bound: T_Number, upper_bound: T_Number) -> T_Number:
        """Compute the step size (interval length) used in the partitions."""
        pass

    @property
    @abstractmethod
    def _partition_center_offset(self) -> T_Number:
        """Offset between center and endpoints of an interval."""
        pass

    def __len__(self) -> int:
        return self._n_partitions


class ContinuousRangePartitioner(RangePartitioner[float]):
    """
    Partition numerical values in successive intervals of the same length.

    The partitions are made of intervals which have all the same length which is a
    number in the series
    (..., 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, ...)

    The interval length is computed based on
    :attr:`max_partitions`, :attr:`lower_bound` and :attr:`upper_bound` by
    :meth:`_step_size`.

    Each partition is an interval whose endpoints are multiple of the interval
    length. The rules used to determine these intervals are that:
    - :attr:`lower_bound` is in the first interval
    - :attr:`upper_bound` is in the last interval

    For example, if the computed interval length is 0.2, some possible
    partitions would be:
    [3.2, 3.4), [3.4, 3.6), [3.6, 3.8), [4.0, 4.2), [4.4, 4.6), [4.6, 4.8]

    :param max_partitions: the max number of partitions to make (default = 20);
      it should be greater or equal than 2
    :param lower_bound: the lower bound of the elements in the partition
    :param upper_bound: the upper bound of the elements in the partition
    """

    def __init__(
        self,
        max_partitions: int = None,
        lower_bound: Optional[T_Number] = None,
        upper_bound: Optional[T_Number] = None,
    ) -> None:
        super().__init__(
            max_partitions=max_partitions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    def _step_size(self, lower_bound: float, upper_bound: float) -> float:
        return RangePartitioner._ceil_step(
            (upper_bound - lower_bound) / (self.max_partitions - 1)
        )

    @property
    def _partition_center_offset(self) -> float:
        return self._step / 2


class IntegerRangePartitioner(RangePartitioner[int]):
    """
    Partition numerical values in intervals of same length with integer bounds.

    The interval length of the partitions is an integer. The
    bounds of the intervals are all integer which are multiple of the interval length.

    The interval length is computed based on
    :attr:`max_partitions`, :attr:`lower_bound` and :attr:`upper_bound` by
    :meth:`_step_size`.

    Each partition is an interval whose endpoints are multiple of the interval
    length. The rules used to determine these intervals are that:
    - :attr:`lower_bound` is in the first interval
    - :attr:`upper_bound` is in the last interval

    Implementations must define :meth:`_step_size` and :meth:`_partition_center_offset`.

    :param max_partitions: the max number of partitions to make (default = 20);
      it should be greater or equal than 2
    :param lower_bound: the lower bound of the elements in the partition
    :param upper_bound: the upper bound of the elements in the partition
    """

    def __init__(
        self,
        max_partitions: int = None,
        lower_bound: Optional[T_Number] = None,
        upper_bound: Optional[T_Number] = None,
    ) -> None:
        super().__init__(
            max_partitions=max_partitions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    def _step_size(self, lower_bound: int, upper_bound: int) -> int:
        """Compute the step size of the central values."""
        return max(
            1,
            int(
                RangePartitioner._ceil_step(
                    (upper_bound - lower_bound) / (self.max_partitions - 1)
                )
            ),
        )

    @property
    def _partition_center_offset(self) -> int:
        return self._step // 2


class CategoryPartitioner(Partitioner[T_Value]):
    """
    Partition categorical values.

    Partition the elements by their values, keeping only the :attr:`max_partitions`
    most frequent values.

    :max_partitions: the maximum number of partitions
    """

    def __init__(self, max_partitions: int = DEFAULT_MAX_PARTITIONS) -> None:
        super().__init__(max_partitions=max_partitions)
        self._max_partitions = max_partitions
        self._frequencies = None
        self._partitions = None

    # noinspection PyMissingOrEmptyDocstring
    def fit(self: T, values: Sequence[T_Value], **fit_params) -> T:
        # we inherit the docstring from the super method
        # (see statement following this method declaration)

        self: CategoryPartitioner  # support type hinting in PyCharm

        value_counts = pd.Series(data=values).value_counts(ascending=False)
        max_partitions = self.max_partitions
        self._partitions = value_counts.index.values[:max_partitions]
        self._frequencies = value_counts.values[:max_partitions]

        return self

    def is_fitted(self) -> bool:
        """``True`` if this partitioner is fitted, else ``False``"""
        return self._frequencies is not None

    def partitions(self) -> Sequence[T_Value]:
        """
        The list of the :attr:`max_partitions` most frequent values.

        :return: the list of most frequent values, ordered decreasingly by the
          frequency"""
        return self._partitions

    def frequencies(self) -> Sequence[int]:
        """
        Return the number of elements in each partitions.

        :return: for each partition, the number of observed values that fall within
          the partition
        """
        return self._frequencies

    @property
    def is_categorical(self) -> bool:
        """```True```"""
        return True

    def __len__(self) -> int:
        return len(self._partitions)
