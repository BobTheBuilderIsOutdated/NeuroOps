"""Local webcam expression controller. No EEG data is produced by this application."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.camera-deps'))
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from statistics import median
from gestures import Gestures
from windows_input import WindowsInput
from gaze import features, GazeModel, Movement
from head_pose import angles, steering


def camera_worker(index, frames, stop, errors):
    capture = None
    try:
        import cv2
        import mediapipe as mp
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT / 'models/face_landmarker.task')),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=2, output_face_blendshapes=True, output_facial_transformation_matrixes=True)
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not capture.isOpened():
            raise RuntimeError('Camera unavailable. Close other camera apps or try another camera index.')
        previous = 0
        with mp.tasks.vision.FaceLandmarker.create_from_options(options) as model:
            while not stop.is_set():
                ok, frame = capture.read()
                stamp = time.monotonic()
                if not ok:
                    raise RuntimeError('Camera stopped delivering frames.')
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                millis = max(previous + 1, int(stamp * 1000))
                previous = millis
                result = model.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), millis)
                scores = None
                if len(result.face_blendshapes) == 1:
                    values = {c.category_name: c.score for c in result.face_blendshapes[0]}
                    scores = ((values.get('mouthSmileLeft', 0) + values.get('mouthSmileRight', 0))/2,
                              values.get('browInnerUp', 0))
                eye = None
                movements = {}
                if scores is not None:
                    eye = features(result.face_landmarks[0])
                    if max(values.get('eyeBlinkLeft', 0), values.get('eyeBlinkRight', 0)) > .45:
                        eye = None
                    movements = {k: values.get(v, 0) for k,v in {
                        'forward':'jawOpen', 'backward':'mouthPucker',
                        'left':'mouthLeft', 'right':'mouthRight'}.items()}
                head = None
                if scores is not None and len(result.facial_transformation_matrixes)==1:
                    head=angles(result.facial_transformation_matrixes[0])
                packet = (stamp, rgb[:, ::-1].copy(), scores, eye, movements, head)
                try:
                    frames.get_nowait()
                except queue.Empty:
                    pass
                frames.put_nowait(packet)
    except Exception as exc:
        errors.put(str(exc))
    finally:
        if capture is not None:
            capture.release()


class Dashboard:
    def __init__(self, root):
        self.root = root
        self.io = WindowsInput()
        self.gestures = Gestures()
        self.gaze = GazeModel()
        self.mover = Movement()
        self.gaze_window = None
        self.gaze_groups = []
        self.gaze_stage = 0
        self.gaze_start = 0
        self.head_center = None
        self.last_head = None
        self.last_head_time = 0
        self.look_mode = tk.StringVar(value='Head')
        self.invert_x = tk.BooleanVar(value=False)
        self.invert_y = tk.BooleanVar(value=False)
        self.gaze_result = tk.StringVar(value='Gaze calibration: not completed')
        self.target_count = tk.StringVar(value='5')
        self.frames, self.errors = queue.Queue(maxsize=1), queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.armed = False
        self.resume_since = None
        self.paused = True
        self.last = 0
        self.release_at = 0
        self.keys = {}
        self.calibration = None
        self.calibration_start = 0
        self.count = 0
        self.output = tk.BooleanVar(value=False)
        self.look = tk.BooleanVar(value=False)
        self.walk = tk.BooleanVar(value=False)
        self.speed = tk.DoubleVar(value=450)
        self.deadzone = tk.DoubleVar(value=.3)
        self.move_threshold = tk.DoubleVar(value=.6)
        self.control_text = tk.StringVar(value='Look: uncalibrated / movement: off')
        self.status = tk.StringVar(value='Ready. Start capture, then calibrate with a relaxed face.')
        self.state = tk.StringVar(value='CONTROL INACTIVE')
        self.connection_text = tk.StringVar(value='Waiting for capture')
        self.smile = tk.DoubleVar(value=.55)
        self.brow = tk.DoubleVar(value=.55)
        root.title('NeuroOps | Head + Gesture Control')
        root.geometry('1000x950')
        root.configure(bg='#0b111a')
        s = ttk.Style(); s.theme_use('clam')
        s.configure('.', background='#0b111a', foreground='#e9f0f8', font=('Segoe UI', 11))
        s.configure('TButton', padding=8, background='#25374e')
        s.configure('TProgressbar', background='#62edb4', troughcolor='#25374e')
        body = ttk.Frame(root, padding=20); body.pack(fill='both', expand=True)
        ttk.Label(body, text='NEUROOPS', font=('Segoe UI', 30, 'bold'), foreground='#62edb4').pack(anchor='w')
        ttk.Label(body, text='GESTURE CONTROL  /  THE PIT CHALLENGE').pack(anchor='w')
        row = ttk.Frame(body); row.pack(fill='x', pady=12)
        self.index = tk.StringVar(value='0')
        ttk.Label(row, text='Camera').pack(side='left')
        ttk.Spinbox(row, from_=0, to=8, width=3, textvariable=self.index).pack(side='left', padx=6)
        for label, fn in [('Start capture', self.start), ('Calibrate neutral', self.calibrate), ('Arm / F8', self.toggle), ('Stop / F9', self.disarm)]:
            ttk.Button(row, text=label, command=fn).pack(side='left', padx=4)
        ttk.Checkbutton(body, text='Enable game output (iw4sp.exe only)', variable=self.output, command=self.disarm).pack(anchor='w')
        row = ttk.Frame(body); row.pack(fill='x', pady=5)
        ttk.Label(row,text='Targets').pack(side='left')
        ttk.Combobox(row,textvariable=self.target_count,values=['5','9'],state='readonly',width=3).pack(side='left',padx=4)
        ttk.Button(row, text='Calibrate gaze', command=self.calibrate_gaze).pack(side='left')
        ttk.Checkbutton(row, text='Mouse-look', variable=self.look, command=self.disarm).pack(side='left', padx=12)
        ttk.Checkbutton(row, text='Gesture WASD', variable=self.walk, command=self.disarm).pack(side='left')
        row=ttk.Frame(body);row.pack(fill='x',pady=5)
        ttk.Label(row,text='Look source').pack(side='left')
        selector=ttk.Combobox(row,textvariable=self.look_mode,values=['Head','Gaze'],state='readonly',width=7)
        selector.pack(side='left',padx=6);selector.bind('<<ComboboxSelected>>',lambda e:self.disarm())
        ttk.Button(row,text='Center head / F6',command=self.center_head).pack(side='left',padx=6)
        ttk.Checkbutton(row,text='Invert horizontal',variable=self.invert_x,command=self.disarm).pack(side='left')
        ttk.Checkbutton(row,text='Invert vertical',variable=self.invert_y,command=self.disarm).pack(side='left')
        row = ttk.Frame(body); row.pack(fill='x')
        for title,var,low,high in [('Look speed',self.speed,50,1200),('Dead zone',self.deadzone,.1,.65),('Movement threshold',self.move_threshold,.25,.9)]:
            ttk.Label(row,text=title).pack(side='left',padx=5)
            ttk.Scale(row,from_=low,to=high,variable=var,command=lambda v:self.disarm()).pack(side='left',fill='x',expand=True)
        ttk.Label(body,textvariable=self.control_text).pack(anchor='w')
        self.look_settings = tk.StringVar()
        ttk.Label(body,textvariable=self.look_settings).pack(anchor='w')
        ttk.Label(body,textvariable=self.gaze_result,wraplength=900).pack(anchor='w')
        ttk.Label(body, textvariable=self.state, font=('Segoe UI', 20), foreground='#62edb4').pack(anchor='w', pady=8)
        ttk.Label(body, textvariable=self.connection_text).pack(anchor='w')
        ttk.Label(body, textvariable=self.status, wraplength=900).pack(anchor='w', pady=5)
        self.preview = ttk.Label(body, text='Capture is off', anchor='center')
        self.preview.pack(fill='x')
        self.bars = []
        for label, variable in [('Smile -> fire', self.smile), ('Raise eyebrows -> reload', self.brow)]:
            row = ttk.Frame(body); row.pack(fill='x', pady=6)
            ttk.Label(row, text=label, width=25).pack(side='left')
            meter = ttk.Progressbar(row, maximum=1, length=210); meter.pack(side='left', padx=8)
            value = ttk.Label(row, text='0.00', width=5); value.pack(side='left')
            ttk.Scale(row, from_=.15, to=.95, variable=variable, command=lambda v: self.update_thresholds()).pack(side='left', fill='x', expand=True)
            self.bars.append((meter, value))
        self.threshold_text = tk.StringVar()
        ttk.Label(body, textvariable=self.threshold_text).pack(anchor='w')
        ttk.Label(body, textvariable=self.status, wraplength=840).pack(anchor='w', pady=10)
        ttk.Label(body, text='F8 arm/disarm | F9 emergency stop | Relax between gestures\nW: open mouth | S: purse lips | A/D: shift mouth left/right\nScores describe facial expressions, not confidence. Frames stay local and are not recorded.').pack(anchor='w')
        self.update_thresholds()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(20, self.tick)

    def disarm(self):
        self.armed = False
        self.paused = True
        self.resume_since = None
        self.gestures.reset()
        self.gaze.reset()
        self.mover.reset()
        self.state.set('CONTROL INACTIVE')
        try:
            self.io.release_all()
        except OSError as exc:
            self.status.set(str(exc))

    def pause_output(self, reason):
        self.paused = True
        self.resume_since = None
        self.gestures.reset(); self.gaze.reset(); self.mover.reset()
        self.io.release_all()
        if self.armed:
            self.state.set('ARMED / PAUSED')
            self.status.set(reason)

    def ready_to_resume(self, scores, movements, stamp):
        if not self.paused:
            return True
        neutral = scores[0] < self.smile.get()*.55 and scores[1] < self.brow.get()*.55
        if self.walk.get():
            neutral = neutral and all(v < self.move_threshold.get()*.6 for v in movements.values())
        if not neutral:
            self.resume_since = None
            self.status.set('Armed: relax your face briefly to resume control.')
            return False
        if self.resume_since is None:
            self.resume_since = stamp
        if stamp-self.resume_since < .25:
            return False
        self.paused = False
        self.state.set('CONTROL ACTIVE' if self.output.get() else 'PREVIEW ACTIVE')
        self.status.set('Tracking recovered / control active. F9 stops output.')
        return True

    def update_thresholds(self):
        self.disarm()
        self.gestures = Gestures(self.smile.get(), self.brow.get())
        self.threshold_text.set(f'Activation thresholds: smile {self.smile.get():.2f} / eyebrows {self.brow.get():.2f}')

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            index = int(self.index.get())
        except ValueError:
            self.status.set('Choose a numeric camera index.'); return
        self.disarm(); self.last = 0
        self.frames, self.errors = queue.Queue(maxsize=1), queue.Queue()
        self.stop = threading.Event()
        self.worker = threading.Thread(target=camera_worker, args=(index, self.frames, self.stop, self.errors), daemon=True)
        self.worker.start()
        self.status.set('Starting capture...')

    def calibrate(self):
        self.disarm()
        if time.monotonic() - self.last > .4:
            self.status.set('Start capture and ensure one face is visible first.'); return
        self.calibration = []
        self.calibration_start = time.monotonic()
        self.status.set('Relax your face for 3 seconds. Do not smile or raise your eyebrows.')

    def toggle(self):
        if self.armed:
            self.disarm(); return
        if self.gaze_window is not None or self.calibration is not None or time.monotonic() - self.last > .4:
            self.status.set('Cannot arm: need a fresh face detection and completed calibration.'); return
        if self.look.get() and self.look_mode.get()=='Head' and self.head_center is None:
            self.status.set('Look straight ahead and click Center head (or press F6).');return
        if self.look.get() and self.look_mode.get()=='Gaze' and self.gaze.weights is None:
            self.status.set(self.gaze_result.get() + ' — mouse-look needs an accepted calibration.'); return
        self.gestures.reset(); self.armed = True
        self.paused = True; self.resume_since = None
        self.state.set('ARMED / WAITING FOR NEUTRAL')
        self.status.set('Relax, then perform one gesture. Return to neutral between triggers.')

    def center_head(self):
        self.disarm()
        if self.last_head is None or time.monotonic()-self.last_head_time>.4:
            self.status.set('Need fresh head tracking. Start capture and face the camera.');return
        self.head_center = self.last_head
        self.status.set('Head centered. Enable mouse-look, select Head, then F8 to arm. No gaze calibration needed.')

    def cancel_gaze(self):
        if self.gaze_window is not None:
            self.gaze_window.destroy(); self.gaze_window = None
            self.gaze_result.set('Gaze calibration cancelled; previous calibration retained.' if self.gaze.weights is not None else 'Gaze calibration cancelled; not calibrated.')
        self.disarm()

    def calibrate_gaze(self):
        self.disarm()
        if time.monotonic()-self.last > .4:
            self.status.set('Start capture and ensure one face is visible first.'); return
        self.cancel_gaze()
        self.calibration = None
        self.gaze_groups = []
        self.gaze_stage = 0
        self.gaze_start = time.monotonic()
        self.gaze_samples = []
        self.targets = ([(0,0),(-1,0),(1,0),(0,-1),(0,1)] if self.target_count.get()=='5'
                        else [(0,0),(-1,0),(-1,-1),(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1)])
        self.gaze_result.set(f'Gaze calibration: collecting {len(self.targets)} targets...')
        self.gaze_window = tk.Toplevel(self.root)
        self.gaze_window.attributes('-fullscreen',True)
        self.gaze_window.bind('<Escape>',lambda e:self.cancel_gaze())
        self.gaze_window.protocol('WM_DELETE_WINDOW',self.cancel_gaze)
        self.target_canvas = tk.Canvas(self.gaze_window,bg='#0b111a',highlightthickness=0)
        self.target_canvas.pack(fill='both',expand=True)

    def gaze_calibration_frame(self, eye, now):
        if self.gaze_window is None: return
        elapsed = now-self.gaze_start
        x,y = self.targets[self.gaze_stage]
        canvas = self.target_canvas
        width,height = max(100,canvas.winfo_width()),max(100,canvas.winfo_height())
        px,py = width*(.5+.36*x),height*(.5+.34*y)
        canvas.delete('all')
        canvas.create_oval(px-16,py-16,px+16,py+16,fill='#62edb4',outline='')
        canvas.create_text(width/2,40,text=f'Look at the dot. Keep your head still. Target {self.gaze_stage+1}/{len(self.targets)} | Esc cancels',fill='white',font=('Segoe UI',18))
        canvas.create_text(width/2,height-50,text=f'{"Settle" if elapsed<1.2 else "Capturing"} | valid samples: {len(self.gaze_samples)}',fill='white',font=('Segoe UI',16))
        if elapsed >= 1.2 and eye is not None: self.gaze_samples.append(eye)
        if elapsed >= 3.7:
            if len(self.gaze_samples)<12:
                if elapsed < 12:
                    return  # allow more time for blinks or slow camera frames
                self.cancel_gaze()
                self.gaze_result.set(f'Calibration failed at target {self.gaze_stage+1}: only {len(self.gaze_samples)} valid eye samples (12 required).')
                self.status.set(self.gaze_result.get())
                messagebox.showwarning('Gaze calibration incomplete',self.gaze_result.get(),parent=self.root)
                return
            self.gaze_groups.append((self.targets[self.gaze_stage], self.gaze_samples))
            self.gaze_stage += 1
            self.gaze_start = now; self.gaze_samples = []
            if self.gaze_stage == len(self.targets):
                self.cancel_gaze()
                self.finish_gaze()

    def finish_gaze(self):
        try:
            error = self.gaze.fit(self.gaze_groups)
            self.deadzone.set(self.gaze.recommended_deadzone)
            self.gaze_result.set(f'Gaze calibration READY — {len(self.gaze_groups)} targets accepted; fit error {error:.3f}.')
            self.status.set(f'Dead zone set to {self.deadzone.get():.2f}. Enable mouse-look and test in preview.')
            messagebox.showinfo('Gaze calibration accepted',self.gaze_result.get()+'\nYou can now enable gaze mouse-look and arm.',parent=self.root)
        except (ValueError, ArithmeticError) as exc:
            retained = ' Previous accepted calibration retained.' if self.gaze.weights is not None else ' Mouse-look remains uncalibrated.'
            self.gaze_result.set('Calibration NOT accepted: '+str(exc)+retained)
            self.status.set(self.gaze_result.get())
            messagebox.showwarning('Gaze calibration not accepted',self.gaze_result.get(),parent=self.root)

    def tick(self):
        now = time.monotonic()
        try:
            self.look_settings.set(f'Look speed: {self.speed.get():.0f} | Circular dead zone: {self.deadzone.get():.2f} | Return to center to stop')
            for key, fn in [(0x75,self.center_head),(0x77, self.toggle), (0x78, self.disarm)]:
                down = self.io.key_down(key)
                if down and not self.keys.get(key):
                    if key == 0x78: self.cancel_gaze()
                    fn()
                self.keys[key] = down
            foreground = self.io.foreground()
            age = now-self.last if self.last else float('inf')
            self.connection_text.set(f'Foreground: {foreground or "unavailable"} | Frame age: {age:.2f}s | Target: iw4sp.exe')
            if self.io.held and (now >= self.release_at or foreground != 'iw4sp.exe'):
                self.io.release()
            if self.output.get() and foreground != 'iw4sp.exe':
                self.pause_output('Armed: switch to MW2, then relax your face to resume.')
            try:
                error = self.errors.get_nowait()
                self.disarm(); self.status.set(error)
            except queue.Empty:
                pass
            try:
                stamp, rgb, scores, eye, movements, *extra = self.frames.get_nowait()
                head = extra[0] if extra else None
            except queue.Empty:
                stamp = None
            # Consume the newest queued frame before evaluating the timeout. A delayed
            # UI tick during fullscreen transitions does not imply the camera stopped.
            if stamp is None and now-self.last > .4 and self.armed:
                self.pause_output('Tracking delayed: input paused until fresh tracking and neutral return.')
            if stamp is not None:
                from PIL import Image, ImageTk
                self.photo = ImageTk.PhotoImage(Image.fromarray(rgb).resize((480, 300)))
                self.preview.configure(image=self.photo, text='')
                if now-stamp > .4 or scores is None:
                    self.pause_output('Tracking interrupted: input paused. Keep one face visible and relax to resume.')
                    self.last = 0
                    self.calibration = None
                    if self.gaze_window is not None:
                        self.gaze_calibration_frame(None, now)
                    if not self.armed:
                        self.status.set('Keep exactly one face visible; tracking is unavailable.')
                else:
                    self.last = stamp
                    self.last_head = head
                    self.last_head_time = stamp if head is not None else 0
                    self.gaze_calibration_frame(eye, now)
                    point = (steering(head,self.head_center,invert_x=self.invert_x.get(),invert_y=self.invert_y.get())
                             if self.look_mode.get()=='Head' else self.gaze.predict(eye))
                    look_text = 'unavailable' if point is None else f'x {point[0]:+.2f}, y {point[1]:+.2f}'
                    self.control_text.set(f'{self.look_mode.get()} look: {look_text} | '+ ' / '.join(f'{k}: {v:.2f}' for k,v in movements.items()))
                    for (meter, label), score in zip(self.bars, scores):
                        meter['value'] = score; label.configure(text=f'{score:.2f}')
                    if self.calibration is not None:
                        self.calibration.append(scores)
                        if now-self.calibration_start >= 3:
                            if len(self.calibration) >= 15:
                                self.smile.set(min(.95, max(.3, median(v[0] for v in self.calibration)+.25)))
                                self.brow.set(min(.95, max(.3, median(v[1] for v in self.calibration)+.25)))
                                self.update_thresholds()
                                self.status.set('Neutral calibrated. Test gestures in preview, adjust thresholds if needed.')
                            else:
                                self.status.set('Too few frames to calibrate. Try again.')
                            self.calibration = None
                    elif self.armed and (not self.output.get() or foreground == 'iw4sp.exe'):
                        if not self.ready_to_resume(scores, movements, stamp):
                            self.root.after(20,self.tick)
                            return
                        if self.look.get():
                            dx,dy = self.gaze.motion(point, stamp, self.speed.get(), self.deadzone.get())
                            if self.output.get() and (dx or dy): self.io.move_mouse(dx,dy)
                        direction = self.mover.feed(movements,stamp,self.move_threshold.get()) if self.walk.get() else None
                        if self.output.get(): self.io.set_movement(direction)
                        if direction:
                            self.gestures.reset()
                            self.status.set(f'Movement: {direction}'+('' if self.output.get() else ' / preview only'))
                            self.root.after(20,self.tick)
                            return
                        binding = self.gestures.feed(*scores, stamp)
                        if binding:
                            if not self.output.get() or self.io.press(binding):
                                self.release_at = time.monotonic()+.05
                                self.count += 1
                                self.status.set(f'{binding.upper()} / {self.count} accepted gestures / '+('input sent' if self.output.get() else 'preview only'))
        except Exception as exc:
            self.disarm(); self.status.set(f'Stopped: {exc}')
        self.root.after(20, self.tick)

    def close(self):
        self.stop.set(); self.cancel_gaze(); self.disarm(); self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk(); Dashboard(root); root.mainloop()
