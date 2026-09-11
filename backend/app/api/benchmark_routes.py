"""Inspectable, offline benchmark releases and defaults."""
from fastapi import APIRouter, HTTPException
from ..engine.benchmark_registry import CURRENT_VERSION, release, dilution_defaults, _version

router = APIRouter(prefix='/api/benchmarks')


@router.get('/releases')
def releases():
    return {'current': CURRENT_VERSION, 'versions': ['2026-07-legacy', CURRENT_VERSION]}


@router.get('/{version}')
def get_release(version: str):
    try:
        snapshot = release(version)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    records = snapshot['records'].values()
    return {'version': version, 'hash': snapshot['hash'], 'record_count': len(snapshot['records']),
            'observed_count': sum(r.status == 'observed' for r in records),
            'source_gaps': snapshot.get('source_gaps', [])}


@router.get('/{version}/vc-defaults')
def vc_defaults(version: str, vertical: str | None = None):
    try:
        snapshot = release(version)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    token = _version.set(version)
    try:
        return {'dataset_version': version, 'dataset_hash': snapshot['hash'],
                'dilution': dilution_defaults(vertical)}
    finally:
        _version.reset(token)
