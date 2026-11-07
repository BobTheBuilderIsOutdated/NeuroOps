import ctypes
import json
import queue
import threading
import unittest
from unittest.mock import patch

from gate import Gate
from cortex import Cortex
from windows_input import Input, WindowsInput


class GateTests(unittest.TestCase):
    def setUp(self):
        self.g = Gate(dwell=.2, neutral=.1, cooldown=.2)

    def rest(self, start=0):
        self.g.feed('neutral', 0, start)
        self.g.feed('neutral', 0, start+.125)

    def test_requires_neutral_before_first_shot(self):
        self.assertFalse(self.g.feed('push', .9, 0))
        self.assertFalse(self.g.feed('push', .9, .25))

    def test_sustained_signal_fires_once(self):
        self.rest()
        self.assertFalse(self.g.feed('push', .9, .25))
        self.assertTrue(self.g.feed('push', .9, .5))
        self.assertFalse(self.g.feed('push', .9, .75))
        self.assertFalse(self.g.feed('push', .9, 1))

    def test_neutral_rearms(self):
        self.rest()
        self.g.feed('push', .9, .25)
        self.g.feed('push', .9, .5)
        self.rest(.625)
        self.g.feed('push', .9, .875)
        self.assertTrue(self.g.feed('push', .9, 1.125))

    def test_low_power_does_not_rearm(self):
        self.rest()
        self.g.feed('push', .9, .25)
        self.g.feed('push', .9, .5)
        self.g.feed('push', .1, .625)
        self.g.feed('push', .1, .75)
        self.g.feed('push', .9, .875)
        self.assertFalse(self.g.feed('push', .9, 1.125))

    def test_spike_or_wrong_action_resets_dwell(self):
        self.rest()
        self.g.feed('push', .9, .25)
        self.g.feed('pull', .9, .375)
        self.assertFalse(self.g.feed('push', .9, .5))
        self.assertFalse(self.g.feed('push', .9, .625))

    def test_gap_requires_fresh_neutral(self):
        self.rest()
        self.g.feed('push', .9, .25)
        self.assertFalse(self.g.feed('push', .9, 2))
        self.assertFalse(self.g.feed('push', .9, 2.25))

    def test_invalid_power_resets(self):
        for value in [float('nan'), float('inf'), -1, 2, None]:
            self.rest()
            self.assertFalse(self.g.feed('push', value, .25))
            self.assertFalse(self.g.ready)


class TransportTests(unittest.TestCase):
    def test_columns_not_hardcoded(self):
        client = Cortex({}, queue.Queue(), threading.Event())
        client.cols = ['pow', 'act']
        class WS:
            def recv(self):
                return json.dumps({'com': [.8, 'push']})
        client.ws = WS()
        client.receive()
        event = client.events.get_nowait()
        self.assertEqual(event[2:], ('push', .8))

    def test_warning_fails_closed(self):
        client = Cortex({}, queue.Queue(), threading.Event())
        class WS:
            def recv(self):
                return json.dumps({'warning': {'code': 103}})
        client.ws = WS()
        with self.assertRaises(RuntimeError):
            client.receive()


class InputTests(unittest.TestCase):
    def test_native_structure_size(self):
        self.assertEqual(ctypes.sizeof(Input), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

    def test_wrong_process_cannot_receive_input(self):
        io = WindowsInput()
        with patch.object(io, 'foreground', return_value='notepad.exe'), patch.object(io, 'send') as send:
            self.assertFalse(io.press('fire'))
            send.assert_not_called()

    def test_release_uses_original_binding(self):
        io = WindowsInput()
        with patch.object(io, 'foreground', return_value='iw4sp.exe'), patch.object(io, 'send') as send:
            self.assertTrue(io.press('fire'))
            io.release()
            self.assertEqual(send.call_args_list[0].args, ('fire',))
            self.assertEqual(send.call_args_list[1].args, ('fire',))
            self.assertTrue(send.call_args_list[1].kwargs['up'])
            self.assertIsNone(io.held)


if __name__ == '__main__':
    unittest.main()
