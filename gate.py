"""Pure signal gate. All times are monotonic seconds, never Cortex wall time."""
import math


class Gate:
    def __init__(self, action='push', threshold=.65, dwell=.25, cooldown=.4, neutral=.2):
        self.action, self.threshold = action, threshold
        self.dwell, self.cooldown, self.neutral = dwell, cooldown, neutral
        self.reset()

    def reset(self):
        self.ready = False
        self.start = self.rest = self.last = None
        self.fired = -float('inf')

    def feed(self, action, power, now):
        if not isinstance(power, (int, float)) or not math.isfinite(power) or not 0 <= power <= 1:
            self.reset()
            return False
        if self.last is not None and (now - self.last > .5 or now < self.last):
            self.reset()
        self.last = now
        if action == 'neutral':
            self.start = None
            if self.rest is None:
                self.rest = now
            if now - self.rest >= self.neutral:
                self.ready = True
            return False
        self.rest = None
        if action != self.action or power < self.threshold:
            self.start = None
            return False
        if not self.ready or now - self.fired < self.cooldown:
            self.start = None
            return False
        if self.start is None:
            self.start = now
        if now - self.start >= self.dwell:
            self.ready = False
            self.start = None
            self.fired = now
            return True
        return False
