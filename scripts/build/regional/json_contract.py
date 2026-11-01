"""Strict JSON for revision-bound private build inputs."""
import json

def _members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member: " + key)
        result[key] = value
    return result

def _constant(value):
    raise ValueError("Non-finite JSON number: " + value)

def loads(value):
    return json.loads(value, object_pairs_hook=_members, parse_constant=_constant)
