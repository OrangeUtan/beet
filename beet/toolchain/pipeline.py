__all__ = [
    "Pipeline",
    "Task",
    "Plugin",
    "PluginError",
    "PluginImportError",
]


from dataclasses import dataclass, field
from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Protocol,
    Set,
    TypeVar,
    Union,
    cast,
)

from .utils import import_from_string

T = TypeVar("T")


class Plugin(Protocol[T]):
    """Protocol for detecting plugins."""

    def __call__(self, ctx: T) -> Any:
        ...


class PluginError(Exception):
    """Raised when a plugin raises an exception."""


class PluginImportError(PluginError):
    """Raised when a plugin couldn't be imported."""


@dataclass
class Task(Generic[T]):
    """A unit of work generated by the pipeline."""

    plugin: Plugin[T]
    iterator: Optional[Iterator[Any]] = None

    def advance(self, ctx: T) -> Optional["Task[T]"]:
        """Make progress on the task and return it unless no more work is necessary."""
        try:
            if self.iterator is None:
                result = self.plugin(ctx)
                self.iterator = iter(
                    cast(Iterable[Any], result) if isinstance(result, Iterable) else []
                )
            for _ in self.iterator:
                return self
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(self.plugin) from exc.with_traceback(
                getattr(exc.__traceback__, "tb_next", exc.__traceback__)
            )
        return None


@dataclass
class Pipeline(Generic[T]):
    """The plugin execution engine."""

    ctx: T
    default_symbol: str = "beet_default"

    plugins: Set[Plugin[T]] = field(default_factory=set)
    tasks: List[Task[T]] = field(default_factory=list)

    def require(self, spec: Union[Plugin[T], str]):
        """Make sure that the specified plugin has been executed."""
        plugin = self.resolve(spec)
        if plugin in self.plugins:
            return

        self.plugins.add(plugin)

        if task := Task(plugin).advance(self.ctx):
            self.tasks.append(task)

    def resolve(self, spec: Union[Plugin[T], str]) -> Plugin[T]:
        """Return the imported plugin if the argument is a dotted path."""
        try:
            return (
                import_from_string(spec, default_member=self.default_symbol)
                if isinstance(spec, str)
                else spec
            )
        except PluginError:
            raise
        except Exception as exc:
            raise PluginImportError(spec) from exc

    def run(self, specs: Iterable[Union[Plugin[T], str]] = ()):
        """Run the specified plugins."""
        for spec in specs:
            self.require(spec)

        while self.tasks:
            if task := self.tasks.pop().advance(self.ctx):
                self.tasks.append(task)
