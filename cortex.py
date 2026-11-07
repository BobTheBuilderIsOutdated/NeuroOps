"""Small synchronous Cortex client, used only from the connection worker."""
import json
import queue
import time
from pathlib import Path


class Cortex:
    def __init__(self, config, events, stop):
        self.config, self.events, self.stop = config, events, stop
        self.ws = None
        self.counter = 0
        self.token = self.session = None
        self.cols = []

    def note(self, message):
        self.events.put(('status', message))

    def receive(self):
        message = json.loads(self.ws.recv())
        if 'com' in message and self.cols:
            values = dict(zip(self.cols, message['com']))
            self.events.put(('sample', time.monotonic(), values.get('act'), values.get('pow')))
        if 'warning' in message:
            # Fail closed; reconnect explicitly after headset/session/profile warnings.
            raise RuntimeError('Cortex state changed. Check Launcher, then reconnect.')
        return message

    def rpc(self, method, **params):
        self.counter += 1
        request_id = self.counter
        self.ws.send(json.dumps(dict(jsonrpc='2.0', id=request_id, method=method, params=params)))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not self.stop.is_set():
            try:
                result = self.receive()
            except self.timeout_error:
                continue
            if result.get('id') == request_id:
                if 'error' in result:
                    # Avoid logging raw server responses that could include credentials.
                    raise RuntimeError(f'{method} failed (Cortex code {result["error"].get("code")}). Check Launcher/profile/access.')
                return result['result']
        raise RuntimeError(f'{method} timed out or was cancelled.')

    def run(self):
        try:
            import websocket
            self.timeout_error = websocket.WebSocketTimeoutException
            opts = {}
            ca = self.config.get('ca_file', '').strip()
            if ca:
                opts['ca_certs'] = str(Path(ca).resolve())
            self.note('Connecting to local Cortex...')
            self.ws = websocket.create_connection('wss://localhost:6868', timeout=1,
                                                  sslopt=opts, http_no_proxy=['localhost', '127.0.0.1'])
            credentials = dict(clientId=self.config['client_id'], clientSecret=self.config['client_secret'])
            access = self.rpc('requestAccess', **credentials)
            if not access.get('accessGranted'):
                raise RuntimeError('Approve NeuroOps in EMOTIV Launcher, then reconnect.')
            auth = self.rpc('authorize', **credentials)
            if auth.get('warning'):
                raise RuntimeError('Resolve the license/EULA notice in Launcher, then reconnect.')
            self.token = auth['cortexToken']
            headsets = self.rpc('queryHeadsets')
            available = [h for h in headsets if h.get('status') == 'connected']
            wanted = self.config.get('headset_id', '').strip()
            if wanted:
                available = [h for h in available if h['id'] == wanted]
            if len(available) != 1:
                raise RuntimeError('Connect one headset in Launcher, or specify its headset_id in config.local.json.')
            headset = available[0]['id']
            self.session = self.rpc('createSession', cortexToken=self.token, headset=headset, status='open')['id']
            self.rpc('setupProfile', cortexToken=self.token, headset=headset,
                     profile=self.config['profile'], status='load')
            sub = self.rpc('subscribe', cortexToken=self.token, session=self.session, streams=['com'])
            streams = [s for s in sub.get('success', []) if s.get('streamName') == 'com']
            if not streams:
                raise RuntimeError('Mental-command subscription failed. Check your Cortex access.')
            self.cols = streams[0]['cols']
            if not {'act', 'pow'}.issubset(self.cols):
                raise RuntimeError('Unexpected mental-command stream columns.')
            self.note('LIVE / waiting for mental commands')
            while not self.stop.is_set():
                try:
                    self.receive()
                except self.timeout_error:
                    continue
        except ImportError:
            self.note('Missing websocket-client. Run setup.ps1 first.')
        except Exception as exc:
            message = str(exc)
            for key in ('client_secret', 'client_id'):
                secret = self.config.get(key)
                if secret:
                    message = message.replace(secret, '[redacted]')
            if self.token:
                message = message.replace(self.token, '[redacted]')
            self.note(message)
        finally:
            if self.ws:
                if self.session and self.token:
                    try:
                        self.ws.send(json.dumps(dict(jsonrpc='2.0', id=99999, method='updateSession',
                            params=dict(cortexToken=self.token, session=self.session, status='close'))))
                    except Exception:
                        pass
                self.ws.close()
            self.events.put(('ended',))
