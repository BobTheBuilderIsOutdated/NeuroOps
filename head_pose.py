"""Head rotation from MediaPipe's canonical-face transformation matrix."""
import math


def angles(matrix):
    import numpy as np
    m=np.asarray(matrix,dtype=float)
    if m.shape!=(4,4) or not np.isfinite(m).all():return None
    # Remove scale/shear before reading the forward axis.
    u,s,v=np.linalg.svd(m[:3,:3])
    if min(s)<1e-6:return None
    r=u@v
    if np.linalg.det(r)<0:return None
    forward=r[:,2]
    yaw=math.degrees(math.atan2(forward[0],forward[2]))
    pitch=math.degrees(math.atan2(-forward[1],math.hypot(forward[0],forward[2])))
    return yaw,pitch


def steering(pose,center,extent=20,invert_x=False,invert_y=False):
    if pose is None or center is None:return None
    delta=[((pose[i]-center[i]+180)%360-180)/extent for i in range(2)]
    # Canonical face uses an upward Y axis; image mouse coordinates point down.
    return [max(-1.5,min(1.5,delta[0]))*(-1 if invert_x else 1),
            max(-1.5,min(1.5,delta[1]))*(-1 if invert_y else 1)]
