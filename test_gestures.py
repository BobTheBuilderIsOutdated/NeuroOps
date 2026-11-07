import unittest
from gestures import Gestures


class GestureTests(unittest.TestCase):
    def test_fire_requires_rest_and_does_not_repeat(self):
        g = Gestures()
        for t in [0, .1, .25]:
            self.assertIsNone(g.feed(.05, .05, t))
        self.assertIsNone(g.feed(.8, .05, .3))
        self.assertEqual(g.feed(.8, .05, .5), 'fire')
        self.assertIsNone(g.feed(.8, .05, .6))
        self.assertIsNone(g.feed(.05, .8, .7))

    def test_ambiguous_expression_requires_rest(self):
        g = Gestures()
        for t in [0, .1, .25]: g.feed(.05, .05, t)
        self.assertIsNone(g.feed(.9, .9, .3))
        self.assertIsNone(g.feed(.9, .05, .5))
        self.assertIsNone(g.feed(.9, .05, .8))

    def test_reload_after_rest(self):
        g = Gestures()
        for t in [0, .1, .25]: g.feed(.05, .05, t)
        self.assertIsNone(g.feed(.05, .8, .3))
        self.assertEqual(g.feed(.05, .8, .5), 'reload')


if __name__ == '__main__': unittest.main()
