"""Helpers shared by the route modules. Wiring only, no business logic."""
from __future__ import annotations

from fastapi import HTTPException, status


def service(fn, *args, **kwargs):
    """Call a service function and map its errors: LookupError is 404, ValueError is 409."""
    try:
        return fn(*args, **kwargs)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
