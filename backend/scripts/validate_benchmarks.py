"""Validate immutable release hashes, schema and every active numeric binding."""
import json
from app.engine.benchmark_registry import DATA, release


def validate():
    manifest = json.loads((DATA / 'benchmarks/manifest.json').read_text(encoding='utf-8'))
    results = []
    for version in manifest['versions']:
        snapshot = release(version)
        def walk(value, path):
            if isinstance(value, dict):
                for key, child in value.items():
                    if not key.startswith('_'):
                        walk(child, path + [key])
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, path + [str(index)])
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                if '/'.join(path) not in snapshot['bindings']:
                    raise ValueError(f'Unclassified numeric benchmark: {path}')
        for key, value in snapshot['datasets'].items():
            walk(value, [key])
        results.append(dict(version=version, hash=snapshot['hash'], records=len(snapshot['records']),
                            observed=sum(r.status == 'observed' for r in snapshot['records'].values())))
    return results


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
