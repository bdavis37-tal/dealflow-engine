"""Versioned benchmark observations, explicit assumptions, and analysis provenance.

No network access during calculation. ContextVars isolate concurrent requests and
nested sensitivity runs. Engine code continues to consume the existing data shapes.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from functools import lru_cache, wraps
from hashlib import sha256
import json
import inspect
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DATA = Path(__file__).resolve().parents[1] / 'data'
CURRENT_VERSION = '2026-09-11'
ENGINE_VERSION = '2.0.0'
_version = ContextVar('benchmark_version', default=CURRENT_VERSION)
_used: ContextVar[set[str] | None] = ContextVar('benchmark_records', default=None)


class BenchmarkRecord(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, frozen=True)
    id: str
    metric: str
    value: float
    statistic: str
    unit: str
    basis: str
    revenue_basis: str = 'not_applicable'
    stage: str | None = None
    business_model: str | None = None
    geography: str | None = None
    size_min: float | None = None
    size_max: float | None = None
    observation_period: str | None = None
    published_date: str | None = None
    retrieved_date: str | None = None
    source_url: str | None = None
    source_locator: str | None = None
    sample_size: int | None = None
    status: Literal['observed', 'derived', 'assumed'] = 'assumed'
    derivation: str | None = None
    limitations: list[str] = Field(default_factory=list)
    usage_rights: str = 'Inherited model assumption; source redistribution not asserted'
    freshness: Literal['current', 'stale', 'unknown'] = 'unknown'

    @model_validator(mode='after')
    def evidence_required(self):
        if self.status != 'assumed' and not all([self.source_url, self.source_locator,
                                                 self.observation_period, self.retrieved_date]):
            raise ValueError('Observed/derived records require source, locator, period and retrieval date')
        if self.status == 'derived' and not self.derivation:
            raise ValueError('Derived records require a derivation')
        if self.size_min is not None and self.size_max is not None and self.size_min >= self.size_max:
            raise ValueError('Invalid size interval')
        return self


class AnalysisEvidence(BaseModel):
    engine_version: str = ENGINE_VERSION
    dataset_version: str
    dataset_hash: str
    input_fingerprint: str
    records: list[BenchmarkRecord]
    observed_count: int
    assumed_count: int
    limitations: list[str]


class VersionedInput(BaseModel):
    benchmark_version: Literal['2026-07-legacy', '2026-09-11'] = CURRENT_VERSION


def policy(key: str, child: str | None = None) -> float:
    value = BenchmarkView('policy')[key]
    return value[child] if child else value


@lru_cache
def release(version: str = CURRENT_VERSION) -> dict:
    # Lookup against a manifest prevents path traversal via API inputs.
    manifest = json.loads((DATA / 'benchmarks/manifest.json').read_text())
    if version not in manifest['versions']:
        raise ValueError(f'Unsupported benchmark version: {version}')
    path = DATA / 'benchmarks' / manifest['versions'][version]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != manifest['hashes'][version]:
        raise ValueError(f'Benchmark release hash mismatch: {version}')
    data = json.loads(raw)
    if data['version'] != version or len({r['id'] for r in data['records']}) != len(data['records']):
        raise ValueError('Mismatched release version or duplicate record IDs')
    data['records'] = {r['id']: BenchmarkRecord.model_validate(r) for r in data['records']}
    data['hash'] = sha256(raw).hexdigest()
    cells = {}
    def index_cells(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                index_cells(child, path + [key])
        elif isinstance(value, list):
            for i, child in enumerate(value):
                index_cells(child, path + [str(i)])
        else:
            cells['/'.join(path)] = value
    index_cells(data['datasets'], [])
    for binding, record_id in data['bindings'].items():
        if record_id not in data['records']:
            raise ValueError(f'Unknown record binding: {binding}')
        if cells.get(binding) != data['records'][record_id].value:
            raise ValueError(f'Binding value mismatch: {binding}')
    return data


def use_record(record_id: str) -> BenchmarkRecord:
    record = release(_version.get())['records'][record_id]
    used = _used.get()
    if used is not None:
        used.add(record_id)
    return record


class TracedDict(dict):
    def __init__(self, data: dict, path: str):
        super().__init__(data)
        self.path = path

    def __getitem__(self, key):
        value = super().__getitem__(key)
        path = f'{self.path}/{key}'
        if isinstance(value, dict):
            return TracedDict(value, path)
        if isinstance(value, list):
            return TracedList(value, path)
        record_id = release(_version.get())['bindings'].get(path)
        if record_id:
            return use_record(record_id).value
        return value

    def values(self):
        return (self[k] for k in self)

    def items(self):
        return ((k, self[k]) for k in self)

    def get(self, key, default=None):
        return self[key] if key in self else default


class TracedList(list):
    def __init__(self, data: list, path: str):
        super().__init__(data)
        self.path = path

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self))) ]
        if index < 0:
            index += len(self)
        value = super().__getitem__(index)
        path = f'{self.path}/{index}'
        if isinstance(value, dict):
            return TracedDict(value, path)
        if isinstance(value, list):
            return TracedList(value, path)
        rid = release(_version.get())['bindings'].get(path)
        return use_record(rid).value if rid else value

    def __iter__(self):
        return (self[i] for i in range(len(self)))


class BenchmarkView(Mapping):
    """Lazy root view selects the request's snapshot, including in old code paths."""
    def __init__(self, family: str):
        self.family = family

    def __getitem__(self, key):
        return TracedDict(release(_version.get())['datasets'][self.family], self.family)[key]

    def __iter__(self):
        return iter(release(_version.get())['datasets'][self.family])

    def __len__(self):
        return len(release(_version.get())['datasets'][self.family])


def resolve(metric: str, basis: str, *, revenue_basis='not_applicable', stage=None,
            business_model=None, geography=None, size=None, as_of=None) -> dict:
    """Hard metric/basis/stage gates; broader cohorts require unspecified dimensions.

    Assumptions never outrank compatible published observations. No cross-stage,
    EV/equity, or ARR/TTM substitution. Ties use date then stable ID.
    """
    candidates, excluded = [], []
    for record in release(_version.get())['records'].values():
        if record.metric != metric:
            continue
        if record.basis != basis or record.revenue_basis != revenue_basis or record.stage != stage:
            excluded.append(record.id)
            continue
        if as_of and record.published_date and record.published_date > as_of:
            excluded.append(record.id)
            continue
        # A specific incompatible cohort cannot be relaxed into a different one.
        if record.business_model not in (None, business_model):
            excluded.append(record.id)
            continue
        if record.geography not in (None, geography):
            excluded.append(record.id)
            continue
        if record.size_min is not None or record.size_max is not None:
            if size is None or (record.size_min is not None and size < record.size_min) or (
                    record.size_max is not None and size >= record.size_max):
                excluded.append(record.id)
                continue
        specificity = sum(x is not None for x in [record.business_model, record.geography,
                                                   record.size_min, record.size_max])
        candidates.append((record.status != 'assumed', specificity, record.published_date or '', record.id))
    if not candidates:
        return dict(record=None, excluded=excluded, fallback_reason='No compatible evidence or assumption')
    record = use_record(max(candidates)[-1])
    relaxed = [name for name, requested in [('business_model', business_model), ('geography', geography)]
               if requested is not None and getattr(record, name) is None]
    if size is not None and record.size_min is None and record.size_max is None:
        relaxed.append('size')
    return dict(record=record, excluded=excluded,
                fallback_reason='Broader cohort: ' + ', '.join(relaxed) if relaxed else None)


def evidence_analysis(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        inp = args[0] if args else next(iter(kwargs.values()))
        version = getattr(inp, 'benchmark_version', None) or CURRENT_VERSION
        if _used.get() is not None and _version.get() == version:
            # Internal sensitivities accumulate into the parent's evidence.
            return func(*args, **kwargs)
        snapshot = release(version)
        version_token = _version.set(version)
        records: set[str] = set()
        used_token = _used.set(records)
        try:
            output = func(*args, **kwargs)
            bound = inspect.signature(func).bind(*args, **kwargs)
            bound.apply_defaults()
            payload = {k: v.model_dump(mode='json') if isinstance(v, BaseModel) else v
                       for k, v in bound.arguments.items()}
            selected = [snapshot['records'][rid] for rid in sorted(records)]
            assumptions = sum(r.status == 'assumed' for r in selected)
            output.evidence = AnalysisEvidence(dataset_version=version, dataset_hash=snapshot['hash'],
                input_fingerprint=sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest(),
                records=selected, observed_count=sum(r.status == 'observed' for r in selected),
                assumed_count=assumptions,
                limitations=(['Some operative benchmarks are inherited assumptions, not verified market observations.']
                             if assumptions else []) + ['Ranges and scenario probabilities are not calibrated confidence estimates.'])
            return output
        finally:
            _used.reset(used_token)
            _version.reset(version_token)
    return wrapped


SOFTWARE_VERTICALS = {'ai_ml_infrastructure', 'ai_enabled_saas', 'b2b_saas', 'vertical_saas', 'developer_tools'}


def dilution_defaults(vertical: str | None = None) -> dict[str, float]:
    view = BenchmarkView('vc')
    result = {field: view['dilution_per_round'][stage]['median_dilution'] for field, stage in {
        'pre_seed_to_seed': 'seed', 'seed_to_a': 'series_a', 'a_to_b': 'series_b',
        'b_to_c': 'series_c', 'c_to_ipo': 'ipo_lockup_dilution'}.items()}
    if vertical in SOFTWARE_VERTICALS:
        for field, stage in [('pre_seed_to_seed', 'seed'), ('seed_to_a', 'series_a'), ('a_to_b', 'series_b')]:
            match = resolve('financing_dilution', 'ownership', stage=stage, business_model='software')
            if match['record']:
                result[field] = match['record'].value
    result['option_pool_expansion'] = 0.0  # Incremental pool only; do not automatically add it to observed dilution.
    return result
