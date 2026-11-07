import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'.camera-deps'))
import math
import unittest
import numpy as np
from head_pose import angles,steering

class HeadTests(unittest.TestCase):
    def test_identity_and_translation(self):
        m=np.eye(4);m[:3,3]=[5,8,10]
        self.assertEqual(angles(m),(0.,-0.))

    def test_yaw_and_scale(self):
        a=math.radians(20);m=np.eye(4)
        m[:3,:3]=np.array([[math.cos(a),0,math.sin(a)],[0,1,0],[-math.sin(a),0,math.cos(a)]])*2
        yaw,pitch=angles(m)
        self.assertAlmostEqual(yaw,20);self.assertAlmostEqual(pitch,0)

    def test_center_and_invert(self):
        self.assertEqual(steering((10,5),(10,5)),[0,0])
        self.assertEqual(steering((30,25),(10,5)),[1,1])
        self.assertEqual(steering((30,25),(10,5),invert_x=True,invert_y=True),[-1,-1])
        self.assertIsNone(steering(None,(0,0)))

    def test_invalid_matrix(self):
        self.assertIsNone(angles(np.zeros((4,4))))
        self.assertIsNone(angles(np.ones((3,3))))
