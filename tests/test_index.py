import multiprocessing as mp
import os
import time
import unittest

import numpy as np

from jina.drivers.helper import array2pb
from jina.enums import FlowOptimizeLevel
from jina.executors.indexers.vector.numpy import NumpyIndexer
from jina.flow import Flow
from jina.main.parser import set_flow_parser
from jina.proto import jina_pb2
from tests import JinaTestCase


def random_docs(num_docs, chunks_per_doc=5, embed_dim=10):
    c_id = 0
    for j in range(num_docs):
        d = jina_pb2.Document()
        for k in range(chunks_per_doc):
            c = d.chunks.add()
            c.embedding.CopyFrom(array2pb(np.random.random([embed_dim])))
            c.chunk_id = c_id
            c.doc_id = j
            c_id += 1
        yield d


def get_result(resp):
    n = []
    for d in resp.search.docs:
        for c in d.chunks:
            n.append([k.match_chunk.chunk_id for k in c.topk_results])
    n = np.array(n)
    # each chunk should return a list of top-100
    np.testing.assert_equal(n.shape[0], 5)
    np.testing.assert_equal(n.shape[1], 100)


class DummyIndexer(NumpyIndexer):
    # the add() function is simply copied from NumpyIndexer
    def add(self, *args, **kwargs):
        pass


class DummyIndexer2(NumpyIndexer):
    # the add() function is simply copied from NumpyIndexer
    def add(self, keys: 'np.ndarray', vectors: 'np.ndarray', *args, **kwargs):
        if len(vectors.shape) != 2:
            raise ValueError('vectors shape %s is not valid, expecting "vectors" to have rank of 2' % vectors.shape)

        if not self.num_dim:
            self.num_dim = vectors.shape[1]
            self.dtype = vectors.dtype.name
        elif self.num_dim != vectors.shape[1]:
            raise ValueError(
                "vectors' shape [%d, %d] does not match with indexers's dim: %d" %
                (vectors.shape[0], vectors.shape[1], self.num_dim))
        elif self.dtype != vectors.dtype.name:
            raise TypeError(
                "vectors' dtype %s does not match with indexers's dtype: %s" %
                (vectors.dtype.name, self.dtype))
        elif keys.shape[0] != vectors.shape[0]:
            raise ValueError('number of key %d not equal to number of vectors %d' % (keys.shape[0], vectors.shape[0]))
        elif self.key_dtype != keys.dtype.name:
            raise TypeError(
                "keys' dtype %s does not match with indexers keys's dtype: %s" %
                (keys.dtype.name, self.key_dtype))

        self.write_handler.write(vectors.tobytes())
        self.key_bytes += keys.tobytes()
        self.key_dtype = keys.dtype.name
        self._size += keys.shape[0]


class MyTestCase(JinaTestCase):

    def tearDown(self) -> None:
        super().tearDown()
        time.sleep(2)

    def test_doc_iters(self):
        a = random_docs(3, 5)
        for d in a:
            print(d)

    def test_simple_route(self):
        f = Flow().add(yaml_path='_forward')
        with f:
            f.index(input_fn=random_docs(10), in_proto=True)

    def test_update_method(self):
        a = DummyIndexer(index_filename='test.bin')
        a.save()
        self.assertFalse(os.path.exists(a.save_abspath))
        self.assertFalse(os.path.exists(a.index_abspath))
        a.add()
        a.save()
        self.assertTrue(os.path.exists(a.save_abspath))
        self.assertFalse(os.path.exists(a.index_abspath))
        self.add_tmpfile(a.save_abspath, a.index_abspath)

        b = DummyIndexer2(index_filename='testb.bin')
        b.save()
        self.assertFalse(os.path.exists(b.save_abspath))
        self.assertFalse(os.path.exists(b.index_abspath))
        b.add(np.array([1, 2, 3]), np.array([[1, 1, 1], [2, 2, 2]]))
        b.save()
        self.assertTrue(os.path.exists(b.save_abspath))
        self.assertTrue(os.path.exists(b.index_abspath))
        self.add_tmpfile(b.save_abspath, b.index_abspath)

    @unittest.skipIf('GITHUB_WORKFLOW' in os.environ, 'skip the network test on github workflow')
    def test_two_client_route_replicas(self):
        fa1 = set_flow_parser().parse_args(['--optimize-level', str(FlowOptimizeLevel.NONE)])
        f1 = Flow(fa1).add(yaml_path='_forward', replicas=3)
        f2 = Flow(optimize_level=FlowOptimizeLevel.IGNORE_GATEWAY).add(yaml_path='_forward', replicas=3)

        # f3 = Flow(optimize_level=FlowOptimizeLevel.FULL).add(yaml_path='_forward', replicas=3)

        def start_client(fl):
            fl.index(input_fn=random_docs(10), in_proto=True)

        with f1:
            self.assertEqual(f1.num_peas, 6)
            t1 = mp.Process(target=start_client, args=(f1,))
            t1.daemon = True
            t2 = mp.Process(target=start_client, args=(f1,))
            t2.daemon = True

            t1.start()
            t2.start()
            time.sleep(5)

        with f2:
            self.assertEqual(f2.num_peas, 6)
            t1 = mp.Process(target=start_client, args=(f2,))
            t1.daemon = True
            t2 = mp.Process(target=start_client, args=(f2,))
            t2.daemon = True

            t1.start()
            t2.start()
            time.sleep(5)

        # with f3.build() as fl3:
        #     self.assertEqual(fl3.num_peas, 4)

    @unittest.skipIf('GITHUB_WORKFLOW' in os.environ, 'skip the network test on github workflow')
    def test_two_client_route(self):
        f = Flow().add(yaml_path='_forward')

        def start_client(fl):
            fl.index(input_fn=random_docs(10), in_proto=True)

        with f:
            t1 = mp.Process(target=start_client, args=(f,))
            t1.daemon = True
            t2 = mp.Process(target=start_client, args=(f,))
            t2.daemon = True

            t1.start()
            t2.start()
            time.sleep(5)

    def test_index(self):
        f = Flow().add(yaml_path='yaml/test-index.yml', replicas=3, separated_workspace=True)
        with f:
            f.index(input_fn=random_docs(1000), in_proto=True)

        for j in range(3):
            self.assertTrue(os.path.exists(f'test2-{j + 1}/test2.bin'))
            self.assertTrue(os.path.exists(f'test2-{j + 1}/tmp2'))
            self.add_tmpfile(f'test2-{j + 1}/test2.bin', f'test2-{j + 1}/tmp2', f'test2-{j + 1}')

        time.sleep(3)
        with f:
            f.search(input_fn=random_docs(1), in_proto=True, output_fn=get_result, top_k=100)


if __name__ == '__main__':
    unittest.main()
