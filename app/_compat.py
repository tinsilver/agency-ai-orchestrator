"""
Python 3.14 compatibility patch for pydantic v1 (used internally by langfuse).

PEP 649 deferred annotations moved class annotations from __annotations__
to __annotate_func__ at metaclass time. This patch resolves them so that
pydantic v1 BaseModel subclasses can be defined on Python 3.14+.

Import this module BEFORE importing langfuse.
"""
import sys
import typing

if sys.version_info >= (3, 14):
    import pydantic.v1.main as _pv1_main

    _orig_new = _pv1_main.ModelMetaclass.__new__

    @typing.no_type_check
    def _patched_new(mcs, name, bases, namespace, **kwargs):
        annotate_func = namespace.get("__annotate_func__")
        if annotate_func and not namespace.get("__annotations__"):
            try:
                namespace["__annotations__"] = annotate_func(1)
            except Exception:
                pass
        return _orig_new(mcs, name, bases, namespace, **kwargs)

    _pv1_main.ModelMetaclass.__new__ = _patched_new
