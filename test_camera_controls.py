import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / '.camera-deps'))
import unittest
from unittest.mock import patch
from gaze import GazeModel, Movement
from windows_input import WindowsInput

class GazeTests(unittest.TestCase):
    def test_nine_point_corners_and_center(self):
        g=GazeModel()
        targets=[(0,0),(-1,0),(-1,-1),(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1)]
        groups=[(p,[[.5+p[0]*.12,p[1]*.08,.5+p[0]*.11,p[1]*.09] for _ in range(15)]) for p in targets]
        g.fit(groups)
        self.assertEqual(g.predict(groups[0][1][0]),[0.,0.])
        for target,samples in groups:
            for a,b in zip(g.predict(samples[0]),target):self.assertAlmostEqual(a,b,delta=.1)
        self.assertGreaterEqual(g.recommended_deadzone,.12)
        self.assertLessEqual(g.recommended_deadzone,.4)

    def test_return_to_center_stops_without_smoothing_tail(self):
        g=GazeModel()
        for t in [0,.05,.1,.15,.2]:g.motion([1,0],t)
        self.assertEqual(g.motion([0,0],.25),(0,0))
        self.assertEqual(g.remainder,[0.,0.])
        self.assertFalse(g.turning)

    def test_radial_deadzone_equal_horizontal_diagonal_speed(self):
        import math
        a,b=GazeModel(),GazeModel()
        total_a=total_b=0
        for i in range(40):
            x,y=a.motion([.6,0],i*.025)
            u,v=b.motion([.6/math.sqrt(2)]*2,i*.025)
            total_a+=math.hypot(x,y);total_b+=math.hypot(u,v)
        self.assertAlmostEqual(total_a,total_b,delta=3)

    def test_calibration_direction(self):
        g=GazeModel()
        groups=[(p,[[.5+p[0]*.12,p[1]*.08,.5+p[0]*.11,p[1]*.09] for _ in range(15)]) for p in [(0,0),(-1,0),(1,0),(0,-1),(0,1)]]
        g.fit(groups)
        for target,samples in groups:
            for a,b in zip(g.predict(samples[0]),target):self.assertAlmostEqual(a,b,delta=.1)

    def test_flat_calibration_rejected(self):
        with self.assertRaises(ValueError):GazeModel().fit([(p,[[.5,0,.5,0]]*15) for p in [(0,0),(-1,0),(1,0),(0,-1),(0,1)]])

    def test_deadzone_and_missing_tracking(self):
        g=GazeModel()
        for t in [0,.05,.1,.15]:self.assertEqual(g.motion([.1,-.1],t),(0,0))
        self.assertEqual(g.motion(None,.2),(0,0))
        self.assertEqual(g.motion([1,0],.25),(0,0))

    def test_long_gap_no_jump(self):
        g=GazeModel();g.motion([1,0],0)
        self.assertGreater(g.motion([1,0],.1)[0],0)
        self.assertEqual(g.motion([1,0],4),(0,0))

class MovementTests(unittest.TestCase):
    def test_hold_and_relax(self):
        m=Movement()
        self.assertIsNone(m.feed({'forward':.9},0))
        for t in [.1,.2,.35]:m.feed({'forward':0},t)
        self.assertIsNone(m.feed({'forward':.9},.4))
        self.assertEqual(m.feed({'forward':.9},.6),'forward')
        self.assertIsNone(m.feed({'forward':0},.7))

    def test_ambiguous_stops(self):
        m=Movement()
        for t in [0,.1,.25]:m.feed({'forward':0,'backward':0},t)
        self.assertIsNone(m.feed({'forward':.9,'backward':.9},.3))

class OutputTests(unittest.TestCase):
    def test_focus_change_releases(self):
        io=WindowsInput()
        with patch.object(io,'send') as send:
            with patch.object(io,'foreground',return_value='iw4sp.exe'):io.set_movement('forward')
            with patch.object(io,'foreground',return_value='notepad.exe'):io.set_movement('forward')
            self.assertIsNone(io.movement)
            self.assertTrue(send.call_args.kwargs['up'])

    def test_release_all(self):
        io=WindowsInput()
        with patch.object(io,'send') as send,patch.object(io,'foreground',return_value='iw4sp.exe'):
            io.set_movement('forward');io.press('fire');io.release_all()
            self.assertIsNone(io.movement);self.assertIsNone(io.held)
            self.assertEqual(sum(bool(c.kwargs.get('up')) for c in send.call_args_list),2)

    def test_mouse_guard(self):
        io=WindowsInput()
        with patch.object(io,'foreground',return_value='notepad.exe'):self.assertFalse(io.move_mouse(100,100))

class RecoveryTests(unittest.TestCase):
    def test_completed_calibration_is_available_to_arm(self):
        a=self.app
        targets=[(0,0),(-1,0),(-1,-1),(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1)]
        a.gaze_groups=[(p,[[.5+p[0]*.12,p[1]*.08,.5+p[0]*.11,p[1]*.09] for _ in range(15)]) for p in targets]
        with patch('webcam.messagebox.showinfo') as notice:
            a.finish_gaze();notice.assert_called_once()
        self.assertIsNotNone(a.gaze.weights)
        self.assertIn('READY',a.gaze_result.get())
        import time
        a.last=time.monotonic();a.look_mode.set('Gaze');a.look.set(True);a.toggle()
        self.assertTrue(a.armed)

    def test_failed_calibration_reason_survives_arm(self):
        a=self.app
        a.gaze_groups=[(p,[[.5,0,.5,0]]*15) for p in [(0,0),(-1,0),(1,0),(0,-1),(0,1)]]
        with patch('webcam.messagebox.showwarning') as notice:
            a.finish_gaze();notice.assert_called_once()
        self.assertIn('NOT accepted',a.gaze_result.get())
        import time
        a.last=time.monotonic();a.look_mode.set('Gaze');a.look.set(True);a.toggle()
        self.assertFalse(a.armed)
        self.assertIn('barely changed',a.status.get())

    def setUp(self):
        import tkinter as tk
        from webcam import Dashboard
        self.root=tk.Tk();self.root.withdraw()
        self.app=Dashboard(self.root)

    def tearDown(self):
        self.app.close()

    def test_pause_keeps_armed_but_releases(self):
        a=self.app;a.armed=True
        with patch.object(a.io,'release_all') as release:
            a.pause_output('test')
            release.assert_called_once()
        self.assertTrue(a.armed);self.assertTrue(a.paused)
        self.assertEqual(a.state.get(),'ARMED / PAUSED')

    def test_resume_requires_neutral(self):
        a=self.app;a.armed=True
        self.assertFalse(a.ready_to_resume((.9,.1),{},0))
        self.assertFalse(a.ready_to_resume((.05,.05),{},.1))
        self.assertFalse(a.ready_to_resume((.05,.05),{},.2))
        self.assertTrue(a.ready_to_resume((.05,.05),{},.4))
        a.disarm();self.assertFalse(a.armed)

    def test_new_frame_consumed_before_old_timeout(self):
        import time,numpy as np
        a=self.app;a.armed=True;a.last=time.monotonic()-2
        a.frames.put((time.monotonic(),np.zeros((24,32,3),dtype=np.uint8),(.05,.05),None,{}))
        with patch.object(a.io,'foreground',return_value='iw4sp.exe'),patch.object(a.io,'key_down',return_value=False),patch.object(a.io,'press') as press:
            a.tick()
            press.assert_not_called()
        self.assertTrue(a.armed)

    def test_lost_face_pauses_and_does_not_disarm(self):
        import time,numpy as np
        a=self.app;a.armed=True;a.last=time.monotonic()
        a.frames.put((time.monotonic(),np.zeros((24,32,3),dtype=np.uint8),None,None,{}))
        with patch.object(a.io,'foreground',return_value='iw4sp.exe'),patch.object(a.io,'key_down',return_value=False),patch.object(a.io,'release_all') as release:
            a.tick();release.assert_called()
        self.assertTrue(a.armed);self.assertTrue(a.paused)
