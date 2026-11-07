"""NeuroOps desktop dashboard. Run with python app.py."""
import csv
from datetime import datetime
import json
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.deps'))
from gate import Gate
from cortex import Cortex
from windows_input import WindowsInput

BG, CARD, FG, MUTED, GREEN = '#0b111a', '#141f2e', '#e9f0f8', '#91a4bc', '#62edb4'


class App:
    def __init__(self, root):
        self.root = root
        root.title('NEUROOPS / The Pit Challenge')
        root.geometry('1040x850')
        root.minsize(960, 760)
        root.configure(bg=BG)
        self.io = WindowsInput()
        self.gate = Gate()
        self.events = queue.Queue()
        self.worker = None
        self.stop = threading.Event()
        self.armed = False
        self.connected = False
        self.last_sample = 0
        self.release_at = 0
        self.count = 0
        self.sim_until = 0
        self.hotkeys = {}
        self.mode = tk.StringVar(value='SIMULATION')
        self.status = tk.StringVar(value='Simulation ready / no game input')
        self.state = tk.StringVar(value='DISARMED')
        self.signal = tk.StringVar(value='neutral / 0.00')
        self.counter = tk.StringVar(value='0')
        self.foreground = tk.StringVar(value='Foreground: —')
        self.binding = tk.StringVar(value='fire')
        self.action = tk.StringVar(value='push')
        self.threshold = tk.DoubleVar(value=.65)
        self.dwell = tk.DoubleVar(value=250)
        self.cooldown = tk.DoubleVar(value=400)
        self.client_id, self.secret, self.profile = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.config = {}
        try:
            self.config = json.loads((ROOT / 'config.local.json').read_text())
            self.client_id.set(self.config.get('client_id', ''))
            self.secret.set(self.config.get('client_secret', ''))
            self.profile.set(self.config.get('profile', ''))
        except (OSError, ValueError):
            pass
        self.style()
        self.build()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(30, self.tick)

    def style(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('.', background=CARD, foreground=FG, font=('Segoe UI', 10))
        s.configure('TFrame', background=BG)
        s.configure('Card.TFrame', background=CARD)
        s.configure('TLabel', background=BG)
        s.configure('TButton', padding=(12, 8), background='#25374e')
        s.map('TButton', background=[('active', '#36506d')])
        s.configure('TEntry', fieldbackground='#213047', foreground=FG, insertcolor=FG)
        s.configure('TCombobox', fieldbackground='#213047', foreground=FG)
        s.configure('TProgressbar', background=GREEN, troughcolor=CARD)

    def label(self, parent, text=None, variable=None, size=10, color=FG):
        item = ttk.Label(parent, text=text, textvariable=variable,
                         font=('Segoe UI', size), foreground=color)
        return item

    def build(self):
        base = ttk.Frame(self.root, padding=26)
        base.pack(fill='both', expand=True)
        top = ttk.Frame(base)
        top.pack(fill='x')
        self.label(top, 'NEUROOPS', size=30, color=GREEN).pack(side='left')
        self.label(top, 'THE PIT CHALLENGE  /  USF BCI', color=MUTED).pack(side='right')
        self.label(base, 'One trained signal. One deliberate action.', size=12, color=MUTED).pack(anchor='w', pady=(0, 16))
        toolbar = ttk.Frame(base)
        toolbar.pack(fill='x')
        mode = ttk.Combobox(toolbar, textvariable=self.mode, values=['SIMULATION', 'LIVE CORTEX'], state='readonly', width=18)
        mode.pack(side='left', padx=(0, 10))
        mode.bind('<<ComboboxSelected>>', lambda e: self.change_mode())
        ttk.Button(toolbar, text='Connect Cortex', command=self.connect).pack(side='left', padx=4)
        ttk.Button(toolbar, text='Disconnect', command=self.disconnect).pack(side='left', padx=4)
        ttk.Button(toolbar, text='Arm / disarm · F8', command=self.toggle).pack(side='left', padx=4)
        ttk.Button(toolbar, text='STOP · F9', command=lambda: self.disarm('Emergency stop')).pack(side='right')
        self.label(base, variable=self.status, color=MUTED).pack(anchor='w', pady=(10, 4))
        self.label(base, variable=self.foreground, color=MUTED).pack(anchor='w')
        stats = ttk.Frame(base)
        stats.pack(fill='x', pady=12)
        for title, var in [('OUTPUT', self.state), ('MENTAL COMMAND / POWER', self.signal), ('TRIGGERS', self.counter)]:
            panel = ttk.Frame(stats)
            panel.pack(side='left', fill='x', expand=True)
            self.label(panel, title, size=9, color=MUTED).pack(anchor='w')
            self.label(panel, variable=var, size=21, color=GREEN).pack(anchor='w')
        self.power = ttk.Progressbar(base, maximum=1)
        self.power.pack(fill='x', pady=(0, 12))
        controls = ttk.Frame(base)
        controls.pack(fill='x')
        for title, var, values in [('Trained action', self.action, ['push', 'pull', 'lift', 'drop', 'left', 'right', 'rotateLeft', 'rotateRight', 'disappear']), ('Game binding', self.binding, ['fire', 'reload', 'interact'])]:
            col = ttk.Frame(controls)
            col.pack(side='left', padx=(0, 20))
            self.label(col, title, color=MUTED).pack(anchor='w')
            combo = ttk.Combobox(col, textvariable=var, values=values, width=16, state='readonly')
            combo.pack()
            combo.bind('<<ComboboxSelected>>', lambda e: self.configure_gate())
        for title, var, low, high in [('Threshold', self.threshold, .1, .95), ('Hold (ms)', self.dwell, 100, 1000), ('Cooldown (ms)', self.cooldown, 100, 1500)]:
            col = ttk.Frame(controls)
            col.pack(side='left', fill='x', expand=True, padx=6)
            label = self.label(col, color=MUTED)
            label.pack(anchor='w')
            def change(value, title=title, var=var, label=label):
                label.config(text=f'{title}: {var.get():.2f}' if title == 'Threshold' else f'{title}: {var.get():.0f}')
                self.configure_gate()
            ttk.Scale(col, from_=low, to=high, variable=var, command=change).pack(fill='x')
            change(None)
        sim = ttk.Frame(base)
        sim.pack(fill='x', pady=12)
        ttk.Button(sim, text='Simulate a command', command=self.simulate).pack(side='left')
        self.label(sim, 'Simulation never sends mouse or keyboard input. Power is not confidence.', color=MUTED).pack(side='left', padx=12)
        self.label(base, 'CORTEX SETUP  /  credentials stay in memory unless you save locally', color=MUTED).pack(anchor='w', pady=(8, 5))
        credentials = ttk.Frame(base)
        credentials.pack(fill='x')
        for title, var, masked in [('Client ID', self.client_id, False), ('Client secret', self.secret, True), ('Trained profile name', self.profile, False)]:
            col = ttk.Frame(credentials)
            col.pack(side='left', fill='x', expand=True, padx=(0, 10))
            self.label(col, title, color=MUTED).pack(anchor='w')
            ttk.Entry(col, textvariable=var, show='•' if masked else '').pack(fill='x')
        ttk.Button(credentials, text='Save locally', command=self.save_config).pack(side='right', anchor='s')
        self.label(base, 'RUN LOG  /  enter the final time displayed by MW2; lower is better', color=MUTED).pack(anchor='w', pady=(18, 6))
        row = ttk.Frame(base)
        row.pack(fill='x')
        self.run_mode = tk.StringVar(value='Conventional')
        self.run_time, self.misses, self.accidental = tk.StringVar(), tk.StringVar(value='0'), tk.StringVar(value='0')
        ttk.Combobox(row, textvariable=self.run_mode, values=['Conventional', 'NeuroOps'], state='readonly', width=15).pack(side='left')
        for name, var in [('Seconds', self.run_time), ('Misses', self.misses), ('Accidental', self.accidental)]:
            self.label(row, name).pack(side='left', padx=(12, 4))
            ttk.Entry(row, textvariable=var, width=7).pack(side='left')
        ttk.Button(row, text='Record run', command=self.record).pack(side='right')
        self.summary = tk.StringVar(value='No recorded runs yet.')
        self.label(base, variable=self.summary, color=GREEN).pack(anchor='w', pady=8)
        self.log = tk.Text(base, height=7, bg=CARD, fg=MUTED, font=('Consolas', 10), relief='flat', state='disabled')
        self.log.pack(fill='both', expand=True)
        self.write('Ready. Train neutral + one command in EmotivBCI. Close EmotivBCI before loading the profile here.')
        self.load_summary()

    def write(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', f'{time.strftime("%H:%M:%S")}  {text}\n')
        if int(self.log.index('end-1c').split('.')[0]) > 200:
            self.log.delete('1.0', '2.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def configure_gate(self):
        self.disarm()
        self.gate = Gate(self.action.get(), self.threshold.get(), self.dwell.get()/1000, self.cooldown.get()/1000)

    def disarm(self, reason=None):
        self.armed = False
        self.state.set('DISARMED')
        self.gate.reset()
        try:
            self.io.release()
        except OSError as exc:
            self.status.set(str(exc))
        if reason:
            self.status.set(reason)

    def toggle(self):
        if self.armed:
            self.disarm('Output disarmed')
            return
        if self.mode.get() == 'LIVE CORTEX' and (not self.connected or time.monotonic()-self.last_sample > .5):
            self.status.set('Cannot arm: connect Cortex and wait for fresh samples.')
            return
        self.gate.reset()
        self.armed = True
        self.state.set('SIM ARMED' if self.mode.get() == 'SIMULATION' else 'LIVE ARMED')
        self.status.set('Wait for neutral, then activate. Live output requires iw4sp.exe in foreground.')

    def change_mode(self):
        self.disconnect()
        self.sim_until = 0
        self.status.set('Simulation ready / no game input' if self.mode.get() == 'SIMULATION' else 'Live mode / connect Cortex to begin')

    def config_values(self):
        return {**self.config, 'client_id': self.client_id.get().strip(),
                'client_secret': self.secret.get().strip(), 'profile': self.profile.get().strip()}

    def save_config(self):
        try:
            (ROOT / 'config.local.json').write_text(json.dumps(self.config_values(), indent=2))
            self.status.set('Saved config.local.json (contains secret; excluded from Git).')
        except OSError as exc:
            messagebox.showerror('Cannot save', str(exc))

    def connect(self):
        if self.worker and self.worker.is_alive():
            self.status.set('Connection already running; disconnect before reconnecting.')
            return
        if self.mode.get() != 'LIVE CORTEX':
            self.status.set('Select LIVE CORTEX first.')
            return
        config = self.config_values()
        if not all(config[k] for k in ['client_id', 'client_secret', 'profile']):
            self.status.set('Enter client ID, secret, and the trained profile name.')
            return
        self.disarm()
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.worker = threading.Thread(target=Cortex(config, self.events, self.stop).run, daemon=True)
        self.worker.start()

    def disconnect(self):
        self.stop.set()
        self.connected = False
        self.last_sample = 0
        self.disarm('Disconnected')

    def simulate(self):
        if self.mode.get() == 'SIMULATION':
            self.sim_until = time.monotonic() + self.dwell.get()/1000 + .3

    def sample(self, action, power, timestamp):
        now = time.monotonic()
        if now-timestamp > .25 or timestamp < self.last_sample:
            self.disarm('Stale samples ignored; re-arm when signal recovers.')
            return
        self.last_sample = timestamp
        if not isinstance(power, (int, float)) or not 0 <= power <= 1 or not isinstance(action, str):
            self.disarm('Invalid signal received')
            return
        self.signal.set(f'{action} / {power:.2f}')
        self.power['value'] = power
        if not self.armed:
            return
        if self.mode.get() == 'LIVE CORTEX' and self.io.foreground() != 'iw4sp.exe':
            self.gate.reset()
            return
        if self.gate.feed(action, power, timestamp):
            if self.mode.get() == 'LIVE CORTEX':
                try:
                    if not self.io.press(self.binding.get()):
                        self.gate.reset()
                        return
                    self.release_at = now + .05
                except OSError as exc:
                    self.disarm(str(exc))
                    return
            self.count += 1
            self.counter.set(str(self.count))
            self.write(f'{self.mode.get()} → {self.binding.get()} / {action} {power:.2f}')

    def tick(self):
        now = time.monotonic()
        try:
            fg = self.io.foreground()
            self.foreground.set(f'Foreground: {fg or "unavailable"}  /  live target: iw4sp.exe')
            for key, handler in [(0x77, self.toggle), (0x78, lambda: self.disarm('Emergency stop'))]:
                down = self.io.key_down(key)
                if down and not self.hotkeys.get(key):
                    handler()
                self.hotkeys[key] = down
            if self.io.held and (now >= self.release_at or fg != 'iw4sp.exe'):
                self.io.release()
            # Bound work per tick to keep stop hotkey responsive.
            for _ in range(100):
                try:
                    event = self.events.get_nowait()
                except queue.Empty:
                    break
                if self.stop.is_set():
                    continue
                if event[0] == 'status':
                    self.status.set(event[1])
                    self.write(event[1])
                elif event[0] == 'ended':
                    self.connected = False
                    self.disarm()
                elif event[0] == 'sample' and self.mode.get() == 'LIVE CORTEX':
                    self.connected = True
                    self.sample(event[2], event[3], event[1])
            if self.mode.get() == 'SIMULATION':
                self.sample(self.action.get() if now < self.sim_until else 'neutral', .9 if now < self.sim_until else 0, now)
            elif self.armed and now-self.last_sample > .5:
                self.disarm('Signal lost / output disarmed')
        except Exception as exc:
            self.disarm(f'Output stopped: {exc}')
        self.root.after(30, self.tick)

    def record(self):
        try:
            import math
            seconds = float(self.run_time.get())
            misses, accidental = int(self.misses.get()), int(self.accidental.get())
            if not math.isfinite(seconds) or seconds <= 0 or misses < 0 or accidental < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror('Invalid run', 'Enter a positive time and nonnegative whole-number counts.')
            return
        path = ROOT / 'runs.csv'
        try:
            exists = path.exists() and path.stat().st_size > 0
            with path.open('a', newline='') as f:
                writer = csv.writer(f)
                if not exists:
                    writer.writerow(['date', 'mode', 'seconds', 'misses', 'accidental', 'binding', 'threshold', 'hold_ms', 'cooldown_ms'])
                writer.writerow([datetime.now().isoformat(timespec='seconds'), self.run_mode.get(), seconds, misses, accidental,
                                 self.binding.get(), self.threshold.get(), round(self.dwell.get()), round(self.cooldown.get())])
            self.load_summary()
            self.write('Run saved to runs.csv. Time and error counts are manually reported.')
        except OSError as exc:
            messagebox.showerror('Cannot save run', str(exc))

    def load_summary(self):
        try:
            with (ROOT / 'runs.csv').open(newline='') as f:
                rows = list(csv.DictReader(f))
            parts = []
            for mode in ['Conventional', 'NeuroOps']:
                values = [float(r['seconds']) for r in rows if r['mode'] == mode]
                if values:
                    parts.append(f'{mode} best: {min(values):.2f}s ({len(values)} runs)')
            self.summary.set('   /   '.join(parts))
        except (OSError, ValueError, KeyError):
            pass

    def close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == '__main__':
    App(tk.Tk()).root.mainloop()
