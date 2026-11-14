#!/usr/bin/env python3
"""Exercise the real HTTP API and retain curl responses as evidence."""
import json
import os
import shlex
import subprocess
from pathlib import Path

base = os.environ.get('API_URL', 'http://localhost:8080').rstrip('/')
out = Path(os.environ.get('EVIDENCE_DIR', '/home/project/evidence'))
out.mkdir(parents=True, exist_ok=True)

def run(name, method, path, expected, data=None):
    command = ['curl', '--silent', '--show-error', '--include', '-X', method,
               base + path]
    if base.startswith('http://localhost'):
        command += ['-H', 'X-Forwarded-Proto: https']
    if data is not None:
        command += ['-H', 'Content-Type: application/json', '-d', json.dumps(data)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    (out / (name + '.txt')).write_text('$ ' + shlex.join(command) + '\n' + result.stdout)
    headers, _, body = result.stdout.partition('\n\n')
    actual = int(headers.splitlines()[0].split()[1])
    assert actual == expected, (name, actual, result.stdout)
    print(name, actual)
    return json.loads(body) if body.strip() else None

account = {'name': 'Sample Customer', 'email': 'sample@example.com',
           'address': '123 Example Street', 'phone_number': '555-0100',
           'date_joined': '2026-11-15'}
created = run('rest-create-done', 'POST', '/accounts', 201, account)
path = '/accounts/' + str(created['id'])
assert run('rest-read-done', 'GET', path, 200)['name'] == account['name']
assert any(x['id'] == created['id'] for x in run('rest-list-done', 'GET', '/accounts', 200))
account['name'] = 'Updated Sample Customer'
assert run('rest-update-done', 'PUT', path, 200, account)['name'] == account['name']
run('rest-delete-done', 'DELETE', path, 204)
run('rest-delete-verification', 'GET', path, 404)
run('kube-app-output', 'GET', '/', 200)
print('All HTTP lifecycle checks passed.')
