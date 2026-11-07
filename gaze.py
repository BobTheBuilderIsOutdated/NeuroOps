"""Calibrated iris-position steering; not a clinical gaze tracker."""
import math


def features(landmarks):
    if len(landmarks) < 478:
        return None
    result = []
    # Project each iris onto its eye's local axes to reduce roll sensitivity.
    for outer, inner, top, bottom, iris in [(33, 133, 159, 145, 468), (362, 263, 386, 374, 473)]:
        a, b, t, d, p = [landmarks[i] for i in (outer, inner, top, bottom, iris)]
        vx, vy = b.x-a.x, b.y-a.y
        width2 = vx*vx+vy*vy
        if width2 < 1e-7:
            return None
        width = math.sqrt(width2)
        if math.hypot(t.x-d.x, t.y-d.y)/width < .12:
            return None  # closed/squinting eyes must not steer
        result.extend([((p.x-a.x)*vx+(p.y-a.y)*vy)/width2,
                       (-(p.x-(t.x+d.x)/2)*vy+(p.y-(t.y+d.y)/2)*vx)/width2])
    return result if all(math.isfinite(v) for v in result) else None


class GazeModel:
    def __init__(self):
        self.weights = None
        self.center = None
        self.scale = None
        self.bias = None
        self.curved = False
        self.recommended_deadzone = .2
        self.reset()

    def reset(self):
        self.filtered = [0., 0.]
        self.last = None
        self.remainder = [0., 0.]
        self.turning = False

    @staticmethod
    def design(values, curved=False):
        import numpy as np
        values = np.atleast_2d(values)
        if curved:
            # Six terms for nine observations, rather than a high-degree interpolator.
            u = (values[:,0]+values[:,2])/2
            v = (values[:,1]+values[:,3])/2
            return np.column_stack((u,v,u*u,u*v,v*v,np.ones(len(values))))
        return np.column_stack((values,np.ones(len(values))))

    def fit(self, groups):
        import numpy as np
        if len(groups) < 5 or any(len(samples) < 12 for _, samples in groups):
            raise ValueError('Need at least five targets with 12 valid samples each.')
        if tuple(groups[0][0]) != (0,0):
            raise ValueError('The first calibration target must be the center.')
        medians = np.array([np.median(samples, axis=0) for _, samples in groups])
        center = medians[0]
        scale = np.std(medians, axis=0)
        if np.max(scale) < .008:
            raise ValueError('Eye positions barely changed. Keep your head still and look at each target.')
        scale = np.maximum(scale, .008)
        curved = len(groups) >= 9
        x = self.design((medians-center)/scale,curved)
        y = np.array([target for target, _ in groups], dtype=float)
        penalties = [.08,.08,.2,.2,.2,.001] if curved else [.08]*4+[.001]
        weights = np.linalg.solve(x.T@x + np.diag(penalties), x.T@y)
        bias = weights[-1].copy()
        error = float(np.sqrt(np.mean((x@weights-bias-y)**2)))
        if not math.isfinite(error) or error > .3:
            raise ValueError(f'Target fit error {error:.3f} exceeds 0.300. Retry with a still head, clear eyes, and less glare.')
        self.weights, self.center, self.scale = weights, center, scale
        self.bias = bias
        self.curved = curved
        resting = np.asarray(groups[0][1],dtype=float)
        resting_x = self.design((resting-center)/scale,curved)
        noise = np.linalg.norm(resting_x@weights-bias,axis=1)
        self.recommended_deadzone = float(np.clip(np.quantile(noise,.95)+.04,.12,.4))
        self.reset()
        return error

    def predict(self, values):
        import numpy as np
        if self.weights is None or values is None:
            return None
        x = self.design((np.asarray(values)-self.center)/self.scale,self.curved)
        point = (x@self.weights-self.bias)[0]
        if not np.isfinite(point).all():
            return None
        return np.clip(point, -1.5, 1.5).tolist()

    def motion(self, point, now, speed=500, deadzone=.25):
        if point is None:
            self.reset(); return 0, 0
        if self.last is None or now-self.last > .25:
            self.reset()
            self.last = now; return 0, 0
        dt = max(0, min(.1, now-self.last)); self.last = now
        # A circular stop zone avoids diagonal bias. Entering its inner radius
        # stops immediately rather than waiting for the smoothing tail to decay.
        radius = math.hypot(*point)
        if radius <= deadzone*.8:
            self.filtered = list(point)
            self.remainder = [0.,0.]
            self.turning = False
            return 0,0
        alpha = 1-math.exp(-dt/.09)
        for i, value in enumerate(point):
            self.filtered[i] += alpha*(value-self.filtered[i])
        radius = math.hypot(*self.filtered)
        if not self.turning and radius <= deadzone:
            self.remainder = [0.,0.]
            return 0,0
        self.turning = True
        magnitude = min(1., max(0., (radius-deadzone)/(1-deadzone)))**1.5
        delta = []
        for i,v in enumerate(self.filtered):
            velocity = v/max(radius,1e-9)*magnitude
            raw = velocity*speed*dt+self.remainder[i]
            whole = int(raw); self.remainder[i] = raw-whole
            delta.append(whole)
        return tuple(delta)


class Movement:
    def __init__(self): self.reset()

    def reset(self):
        self.candidate = None; self.since = None; self.neutral_since = None
        self.ready = False; self.last = None

    def feed(self, scores, now, threshold=.6):
        if self.last is not None and now-self.last > .3: self.reset()
        self.last = now
        candidates = [k for k,v in scores.items() if v >= threshold]
        if all(v < threshold*.6 for v in scores.values()):
            if self.neutral_since is None: self.neutral_since = now
            if now-self.neutral_since >= .2: self.ready = True
        else: self.neutral_since = None
        if len(candidates) != 1:
            self.candidate = None; self.since = None
            return None
        key = candidates[0]
        if not self.ready: return None
        if key != self.candidate:
            self.candidate = key; self.since = now
        return key if now-self.since >= .18 else None
