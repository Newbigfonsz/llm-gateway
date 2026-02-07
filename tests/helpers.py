"""
Helper functions for LLM Gateway tests.
"""

import sys
import json
import importlib.util
from pathlib import Path


def load_handler_module(handler_name):
    """Load a handler module from the lambda directory.

    We need this because 'lambda' is a Python reserved keyword,
    so we can't use normal imports like 'from lambda.gateway.handler'.
    """
    lambda_dir = Path(__file__).parent.parent / "lambda"
    handler_path = lambda_dir / handler_name / "handler.py"

    spec = importlib.util.spec_from_file_location(f"{handler_name}_handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{handler_name}_handler"] = module
    spec.loader.exec_module(module)
    return module


def make_api_gateway_event(path, method='GET', headers=None, body=None, query_params=None):
    """Helper to create API Gateway v2 event format."""
    event = {
        'rawPath': path,
        'requestContext': {
            'http': {
                'method': method,
                'path': path
            }
        },
        'headers': headers or {},
        'queryStringParameters': query_params
    }

    if body:
        event['body'] = json.dumps(body) if isinstance(body, dict) else body

    return event
