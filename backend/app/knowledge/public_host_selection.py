"""Request-local execution selection for public Knowledge retrieval.

The public PD route uses lexical retrieval and its own PD model for dialogue;
native SD requests keep their original model routing and PEP.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_public_host_retrieval = ContextVar("public_host_knowledge_retrieval", default=False)


@contextmanager
def use_public_host_retrieval():
    token = _public_host_retrieval.set(True)
    try:
        yield
    finally:
        _public_host_retrieval.reset(token)


def public_host_retrieval_selected() -> bool:
    return _public_host_retrieval.get()
