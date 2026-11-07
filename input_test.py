"""User-triggered input diagnostics. Does not open a camera or alter calibration."""
import time
import tkinter as tk
from tkinter import ttk
from windows_input import WindowsInput


class InputTest:
    def __init__(self, root):
        self.root = root
        self.io = WindowsInput()
        self.keys = {}
        self.release_at = 0
        root.title('NeuroOps | MW2 input test')
        root.geometry('680x420')
        self.status = tk.StringVar(value='No input sent. Switch to MW2, then press a test key.')
        self.foreground = tk.StringVar()
        frame=ttk.Frame(root,padding=20);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='MW2 INPUT TEST',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Press F9 first to stop the main controller. Leave both apps open.\nSwitch to MW2 campaign and test one key at a time.\n\nF6: tap R (reload, 150 ms)\nF7: move the view slightly right\nF10: hold W for 300 ms\nF9: release all test inputs\n\nAlt-Tab back here to read the results.',font=('Segoe UI',12)).pack(anchor='w',pady=10)
        ttk.Label(frame,textvariable=self.foreground).pack(anchor='w')
        ttk.Label(frame,textvariable=self.status,wraplength=630).pack(anchor='w',pady=10)
        self.log=tk.Text(frame,height=4,state='disabled');self.log.pack(fill='both',expand=True)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(15,self.tick)

    def note(self,text):
        self.status.set(text)
        self.log.configure(state='normal');self.log.insert('end',time.strftime('%H:%M:%S')+' '+text+'\n');self.log.see('end');self.log.configure(state='disabled')

    def tick(self):
        try:
            fg=self.io.foreground();self.foreground.set('Current foreground: '+fg)
            if (self.io.held or self.io.movement) and (time.monotonic()>=self.release_at or fg!='iw4sp.exe'):
                self.io.release_all()
            for key in [0x75,0x76,0x78,0x79]:
                down=self.io.key_down(key)
                if down and not self.keys.get(key):
                    if key==0x78:
                        self.io.release_all();self.note('Test output stopped.')
                    elif fg!='iw4sp.exe':
                        self.note('Blocked: game is not foreground ('+fg+').')
                    elif key==0x75:
                        if self.io.press('reload'):
                            self.release_at=time.monotonic()+.15
                            self.note('R accepted by Windows. Did the game reload?')
                        else:self.note('Focus changed before sending R.')
                    elif key==0x76:
                        if self.io.move_mouse(60,0):self.note('Mouse movement accepted by Windows. Did the view turn right?')
                        else:self.note('Focus changed before mouse movement.')
                    elif key==0x79:
                        self.io.set_movement('forward')
                        self.release_at=time.monotonic()+.3
                        self.note('W submitted. Did the character move forward?')
                self.keys[key]=down
        except Exception as exc:
            self.note('Input error: '+str(exc))
            try:self.io.release_all()
            except OSError:pass
        self.root.after(15,self.tick)

    def close(self):
        self.io.release_all();self.root.destroy()


if __name__=='__main__':
    root=tk.Tk();InputTest(root);root.mainloop()
