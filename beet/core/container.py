__all__ = [
    "MatchMixin",
    "SupportsMerge",
    "MergeMixin",
    "Pin",
    "Container",
    "ContainerProxy",
]


from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from pathspec import PathSpec

from .utils import SENTINEL_OBJ, Sentinel


class MatchMixin:
    def match(self: Mapping[str, object], *patterns: str) -> Set[str]:
        """Return keys matching the given path patterns."""
        spec = PathSpec.from_lines("gitwildmatch", patterns or ["*"])
        return set(spec.match_files(self.keys()))


K = TypeVar("K")
V = TypeVar("V")


class SupportsMerge(Protocol[V]):
    """Protocol for detecting mergeable types."""

    def merge(self: V, other: V) -> bool:
        ...


MergeableType = TypeVar("MergeableType", bound="SupportsMerge[object]")


class MergeMixin:
    def merge(
        self: MutableMapping[K, MergeableType], other: Mapping[K, MergeableType]
    ) -> bool:
        """Merge values from the given dict-like object."""
        for key, value in other.items():
            try:
                if self[key].merge(value):
                    continue
            except KeyError:
                pass
            self[key] = value
        return True


PinType = TypeVar("PinType", bound="Pin[object]")


PinDefault = Union[V, Sentinel]
PinDefaultFactory = Union[Callable[[], V], Sentinel]


@dataclass
class Pin(Generic[V]):
    key: Any
    default: PinDefault[V] = SENTINEL_OBJ
    default_factory: PinDefaultFactory[V] = SENTINEL_OBJ

    def __get__(self, obj: Any, objtype: Optional[Type[object]] = None) -> V:
        mapping = self.forward(obj)

        try:
            return mapping[self.key]
        except KeyError:
            value = (
                self.default
                if isinstance(self.default_factory, Sentinel)
                else self.default_factory()
            )

            if isinstance(value, Sentinel):
                raise

            mapping[self.key] = value
            return self.__get__(obj, objtype)

    def __set__(self, obj: Any, value: V):
        self.forward(obj)[self.key] = value

    def __delete__(self, obj: Any):
        del self.forward(obj)[self.key]

    def forward(self, obj: Any) -> Any:
        """Return the dict-like object that contains the pinned value."""
        return obj

    @classmethod
    def collect_from(cls: Type[PinType], target: Type[object]) -> Dict[str, PinType]:
        return {
            key: cast(PinType, value)
            for key, value in vars(target).items()
            if isinstance(value, cls)
        }


class Container(MergeMixin, MutableMapping[K, V]):
    """Generic dict-like container.

    The class wraps a builtin dictionnary and exposes overrideable hooks
    for intercepting updates and missing items.
    """

    _wrapped: Dict[K, V]

    def __init__(self):
        self._wrapped = {}

    def __getitem__(self, key: K) -> V:
        try:
            return self._wrapped[key]
        except KeyError:
            pass

        value = self.missing(key)
        self[key] = value
        return value

    def __setitem__(self, key: K, value: V):
        self._wrapped[key] = self.process(key, value)

    def __delitem__(self, key: K):
        del self._wrapped[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self._wrapped)

    def __len__(self) -> int:
        return len(self._wrapped)

    def process(self, key: K, value: V) -> V:
        """Process the value before inserting it."""
        return value

    def missing(self, key: K) -> V:
        """Recover missing item or raise a KeyError."""
        raise KeyError(key)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(keys={list(self.keys())})"


ProxyKeyType = TypeVar("ProxyKeyType")


class ContainerProxy(Generic[ProxyKeyType, K, V], MergeMixin, MutableMapping[K, V]):
    """Generic aggregated view over several nested bounded dict-like objects."""

    proxy: Mapping[K, Mapping[ProxyKeyType, MutableMapping[K, V]]]
    proxy_key: ProxyKeyType

    def __init__(
        self,
        proxy: Mapping[K, Mapping[ProxyKeyType, MutableMapping[K, V]]],
        proxy_key: ProxyKeyType,
    ) -> None:
        self.proxy = proxy
        self.proxy_key = proxy_key

    def __getitem__(self, key: K) -> V:
        key1, key2 = self.split_key(key)
        return self.proxy[key1][self.proxy_key][key2]

    def __setitem__(self, key: K, value: V):
        key1, key2 = self.split_key(key)
        self.proxy[key1][self.proxy_key][key2] = value

    def __delitem__(self, key: K):
        key1, key2 = self.split_key(key)
        del self.proxy[key1][self.proxy_key][key2]

    def __iter__(self) -> Iterator[K]:
        for key1, mapping in self.proxy.items():
            for key2 in mapping[self.proxy_key]:
                yield self.join_key(key1, key2)

    def __len__(self) -> int:
        return sum(len(mapping[self.proxy_key]) for mapping in self.proxy.values())

    def split_key(self, key: K) -> Tuple[K, K]:
        """Return the outer mapping key and the nested key."""
        raise NotImplementedError()

    def join_key(self, key1: K, key2: K) -> K:
        """Combine the outer mapping key and the nested key."""
        raise NotImplementedError()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(keys={list(self.keys())})"
