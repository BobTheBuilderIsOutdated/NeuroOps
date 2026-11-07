"""Windows foreground-checked input. No hooks, injection into processes, or game reads."""
import ctypes
from ctypes import wintypes as W
import os

ULONG_PTR = ctypes.c_size_t


class Mouse(ctypes.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class Keyboard(ctypes.Structure):
    _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD),
                ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class Payload(ctypes.Union):
    _fields_ = [('mi', Mouse), ('ki', Keyboard)]


class Input(ctypes.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', W.DWORD), ('data', Payload)]


class WindowsInput:
    def __init__(self):
        self.u = ctypes.WinDLL('user32', use_last_error=True)
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.u.GetForegroundWindow.restype = W.HWND
        self.u.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        self.u.SendInput.argtypes = [W.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.u.SendInput.restype = W.UINT
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        self.k.CloseHandle.argtypes = [W.HANDLE]
        self.held = None
        self.movement = None

    def foreground(self):
        pid = W.DWORD()
        self.u.GetWindowThreadProcessId(self.u.GetForegroundWindow(), ctypes.byref(pid))
        handle = self.k.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return ''
        try:
            size = W.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if self.k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
            return ''
        finally:
            self.k.CloseHandle(handle)

    def key_down(self, vk):
        return bool(self.u.GetAsyncKeyState(vk) & 0x8000)

    def send(self, binding, up=False):
        item = Input()
        if binding == 'fire':
            item.type = 0
            item.mi.dwFlags = 0x0004 if up else 0x0002
        else:
            item.type = 1
            item.ki.wScan = {'reload': 0x13, 'interact': 0x12, 'forward': 0x11,
                             'backward': 0x1f, 'left': 0x1e, 'right': 0x20}[binding]
            item.ki.dwFlags = 0x0008 | (0x0002 if up else 0)
        if self.u.SendInput(1, ctypes.byref(item), ctypes.sizeof(Input)) != 1:
            raise OSError('Windows rejected the input. Check game/app privilege levels.')

    def press(self, binding):
        if self.foreground() != 'iw4sp.exe':
            return False
        self.release()
        self.held = binding
        try:
            self.send(binding)
        except Exception:
            self.release()
            raise
        return True

    def release(self):
        if self.held:
            binding = self.held
            self.send(binding, up=True)
            self.held = None

    def set_movement(self, direction):
        if direction not in (None, 'forward', 'backward', 'left', 'right'):
            raise ValueError('Invalid movement binding')
        if direction and self.foreground() != 'iw4sp.exe':
            direction = None
        if direction == self.movement:
            return
        if self.movement:
            self.send(self.movement, up=True)
            self.movement = None
        if direction:
            self.movement = direction
            self.send(direction)

    def release_all(self):
        try:
            self.release()
        finally:
            self.set_movement(None)

    def move_mouse(self, dx, dy):
        if self.foreground() != 'iw4sp.exe':
            return False
        item = Input()
        item.type = 0
        item.mi.dx = max(-100, min(100, int(dx)))
        item.mi.dy = max(-100, min(100, int(dy)))
        item.mi.dwFlags = 0x0001
        if self.u.SendInput(1, ctypes.byref(item), ctypes.sizeof(Input)) != 1:
            raise OSError('Windows rejected mouse movement.')
        return True
