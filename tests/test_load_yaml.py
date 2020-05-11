import unittest

import ruamel.yaml

from jina.helper import expand_env_var
from jina.logging import default_logger
from tests import JinaTestCase


class MyTestCase(JinaTestCase):

    def test_load_yaml1(self):
        from jina.executors.indexers.vector.numpy import NumpyIndexer
        NumpyIndexer.load_config('yaml/dummy_exec1.yml')
        self.add_tmpfile('test.gzip')

    def test_load_yaml2(self):
        from jina.executors import BaseExecutor
        a = BaseExecutor.load_config('yaml/dummy_exec1.yml')
        a.close()
        self.add_tmpfile('test.gzip')
        b = BaseExecutor.load_config('yaml/dummy_exec1.yml')
        b.save()
        self.add_tmpfile(b.save_abspath)
        b.save_config()
        self.add_tmpfile(b.config_abspath)
        b.close()

    def test_load_external(self):
        from jina.executors import BaseExecutor
        self.assertRaises(ruamel.yaml.constructor.ConstructorError, BaseExecutor.load_config, 'yaml/dummy_ext_exec.yml')

        b = BaseExecutor.load_config('yaml/dummy_ext_exec_sucess.yml')
        self.assertEqual(b.__class__.__name__, 'DummyExternalIndexer')

    def test_expand_env(self):
        print(expand_env_var('${PATH}-${AA}'))
        default_logger.info('aa')
        default_logger.success('aa')


if __name__ == '__main__':
    unittest.main()
