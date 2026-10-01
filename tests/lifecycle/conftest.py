"""Private synthetic producers over the existing isolated PostgreSQL17 fixture."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('lifecycle_founder_fixture',Path(__file__).parents[1]/'founder/conftest.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
flow_engine = shared.flow_engine
identities = shared.identities
enabled = shared.enabled
migrate = shared.migrate
