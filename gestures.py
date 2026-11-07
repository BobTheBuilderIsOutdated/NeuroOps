"""Expression scores and mutually exclusive command decisions."""
from gate import Gate


class Gestures:
    def __init__(self, smile=.55, brow=.55):
        self.thresholds = {'fire': smile, 'reload': brow}
        self.gates = {k: Gate(k, v, .18, .6, .2) for k, v in self.thresholds.items()}

    def reset(self):
        for gate in self.gates.values():
            gate.reset()

    def feed(self, smile, brow, now):
        scores = {'fire': smile, 'reload': brow}
        active = [k for k in scores if scores[k] >= self.thresholds[k]]
        # Both expressions at once are ambiguous; require relaxation before retrying.
        if len(active) > 1:
            self.reset()
            return None
        neutral = all(scores[k] < self.thresholds[k] * .55 for k in scores)
        command = active[0] if active else ('neutral' if neutral else 'pending')
        fired = None
        for key, gate in self.gates.items():
            if gate.feed(command, scores[key], now):
                fired = key
        if fired:
            self.reset()  # shared neutral reset prevents cross-expression double triggers
        return fired
