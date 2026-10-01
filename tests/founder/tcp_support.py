"""Own only these ephemeral loopback API processes; never use a pre-existing port."""
from contextlib import contextmanager
import os
import socket
import subprocess
import sys
import time
import httpx

CHILD = r"""
import os,re
from sqlalchemy import create_engine
from returnops_api.main import create_app
from returnops_api.customer_config import load_private_auth_config
import uvicorn
schema=os.environ['RETURNOPS_TEST_SCHEMA']
assert re.fullmatch(r'customer_test_[0-9a-f]{32}',schema)
engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,pool_size=4,max_overflow=4,
    connect_args={'options':'-c search_path='+schema+' -c statement_timeout=10000'})
app=create_app(engine=engine,auth_config=load_private_auth_config(),enable_processor=False)
uvicorn.run(app,host='127.0.0.1',port=int(os.environ['RETURNOPS_TEST_PORT']),access_log=False,log_level='warning')
"""


@contextmanager
def api_process(engine, auth_file, log):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    env = os.environ.copy()
    env.update(RETURNOPS_AUTH_FILE=str(auth_file), RETURNOPS_TEST_SCHEMA=engine._customer_test_schema,
               RETURNOPS_TEST_PORT=str(port), PYTHONDONTWRITEBYTECODE='1')
    with log.open('wb') as output:
        process = subprocess.Popen([sys.executable, '-B', '-c', CHILD], env=env, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        url = 'http://127.0.0.1:' + str(port)
        try:
            ready = False
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    if httpx.get(url + '/health/ready', timeout=1).status_code == 200:
                        ready = True
                        break
                except httpx.RequestError:
                    pass
                time.sleep(.05)
            assert ready, 'Owned Founder API did not become ready'
            yield url, process.pid
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            assert process.poll() is not None
