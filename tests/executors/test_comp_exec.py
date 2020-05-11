import os
import unittest

from jina.executors import BaseExecutor
from jina.executors.compound import CompoundExecutor
from tests import JinaTestCase


class dummyA(BaseExecutor):
    def say(self):
        return 'a'

    def sayA(self):
        print('A: im A')


class dummyB(BaseExecutor):
    def say(self):
        return 'b'

    def sayB(self):
        print('B: im B')


class MyTestCase(JinaTestCase):
    def test_compositional_route(self):
        da = dummyA()
        db = dummyB()
        a = CompoundExecutor()

        a.components = lambda: [da, db]
        self.assertEqual(a.say_all(), ['a', 'b'])
        with self.assertRaises(AttributeError):
            a.say()

        b = CompoundExecutor({'say': {da.name: 'say'}})
        b.components = lambda: [da, db]
        self.assertEqual(b.say_all(), ['a', 'b'])
        self.assertEqual(b.say(), 'a')
        b.add_route('say', db.name, 'say')
        self.assertEqual(b.say(), 'b')
        b.save_config()
        self.assertTrue(os.path.exists(b.config_abspath))

        c = BaseExecutor.load_config(b.config_abspath)
        self.assertEqual(c.say_all(), ['a', 'b'])
        self.assertEqual(c.say(), 'a')

        b.add_route('say', db.name, 'say', is_stored=True)
        b.save_config()
        c = BaseExecutor.load_config(b.config_abspath)
        self.assertEqual(c.say_all(), ['a', 'b'])
        self.assertEqual(c.say(), 'b')

        b.touch()
        b.save()
        self.assertTrue(os.path.exists(b.save_abspath))

        d = BaseExecutor.load(b.save_abspath)
        self.assertEqual(d.say_all(), ['a', 'b'])
        self.assertEqual(d.say(), 'b')

        self.tmp_files.append(b.config_abspath)
        self.tmp_files.append(b.save_abspath)

    def test_compositional_dump(self):
        a = CompoundExecutor()
        a.components = lambda: [BaseExecutor(), BaseExecutor()]
        self.assertIsNotNone(a.name)
        self.tmp_files.append(a.save_abspath)
        self.tmp_files.append(a.config_abspath)
        a.touch()
        a.save()
        a.save_config()
        self.assertTrue(os.path.exists(a.save_abspath))
        self.assertTrue(os.path.exists(a.config_abspath))

    def test_compound_from_yaml(self):
        a = BaseExecutor.load_config('../yaml/npvec.yml')
        for c in a.components:
            self.add_tmpfile(c.index_abspath)
        self.assertTrue(isinstance(a, CompoundExecutor))
        self.assertTrue(callable(getattr(a, 'add')))
        self.assertTrue(callable(getattr(a, 'query')))
        self.assertTrue(callable(getattr(a, 'meta_add')))
        self.assertTrue(callable(getattr(a, 'meta_query')))


if __name__ == '__main__':
    unittest.main()
