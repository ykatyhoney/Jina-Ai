import unittest

import requests

from jina import JINA_GLOBAL
from jina.enums import FlowOptimizeLevel
from jina.flow import Flow
from jina.main.checker import NetworkChecker
from jina.main.parser import set_pea_parser, set_ping_parser
from jina.main.parser import set_pod_parser
from jina.peapods.pea import BasePea
from jina.peapods.pod import BasePod
from jina.proto import jina_pb2
from tests import JinaTestCase


def random_docs(num_docs, chunks_per_doc=5, embed_dim=10):
    c_id = 0
    for j in range(num_docs):
        d = jina_pb2.Document()
        for k in range(chunks_per_doc):
            c = d.chunks.add()
            c.text = 'i\'m chunk %d from doc %d' % (c_id, j)
            c.chunk_id = c_id
            c.doc_id = j
            c_id += 1
        d.meta_info = b'hello world'
        yield d


def random_queries(num_docs, chunks_per_doc=5, embed_dim=10):
    for j in range(num_docs):
        d = jina_pb2.Document()
        for k in range(chunks_per_doc):
            dd = d.topk_results.add()
            dd.match_doc.doc_id = k
        yield d


class MyTestCase(JinaTestCase):

    def test_ping(self):
        a1 = set_pea_parser().parse_args([])
        a2 = set_ping_parser().parse_args(['0.0.0.0', str(a1.port_ctrl), '--print-response'])
        a3 = set_ping_parser().parse_args(['0.0.0.1', str(a1.port_ctrl), '--timeout', '1000'])

        with self.assertRaises(SystemExit) as cm:
            with BasePea(a1):
                NetworkChecker(a2)

        self.assertEqual(cm.exception.code, 0)

        # test with bad addresss
        with self.assertRaises(SystemExit) as cm:
            with BasePea(a1):
                NetworkChecker(a3)

        self.assertEqual(cm.exception.code, 1)

    def test_flow_with_jump(self):
        f = (Flow().add(name='r1', yaml_path='_forward')
             .add(name='r2', yaml_path='_forward')
             .add(name='r3', yaml_path='_forward', needs='r1')
             .add(name='r4', yaml_path='_forward', needs='r2')
             .add(name='r5', yaml_path='_forward', needs='r3')
             .add(name='r6', yaml_path='_forward', needs='r4')
             .add(name='r8', yaml_path='_forward', needs='r6')
             .add(name='r9', yaml_path='_forward', needs='r5')
             .add(name='r10', yaml_path='_merge', needs=['r9', 'r8']))

        with f:
            f.dry_run()
        f.save_config('tmp.yml')
        Flow.load_config('tmp.yml')

        with Flow.load_config('tmp.yml') as fl:
            fl.dry_run()

        self.add_tmpfile('tmp.yml')

    def test_simple_flow(self):
        bytes_gen = (b'aaa' for _ in range(10))

        def bytes_fn():
            for _ in range(100):
                yield b'aaa'

        f = (Flow()
             .add(yaml_path='_forward'))

        with f:
            f.index(input_fn=bytes_gen)

        with f:
            f.index(input_fn=bytes_fn)

        with f:
            f.index(input_fn=bytes_fn)
            f.index(input_fn=bytes_fn)

    def test_load_flow_from_yaml(self):
        with open('yaml/test-flow.yml') as fp:
            a = Flow.load_config(fp)
            with open('yaml/swarm-out.yml', 'w') as fp, a:
                a.to_swarm_yaml(fp)
            self.add_tmpfile('yaml/swarm-out.yml')

    def test_flow_identical(self):
        with open('yaml/test-flow.yml') as fp:
            a = Flow.load_config(fp)

        b = (Flow()
             .add(name='chunk_seg', replicas=3)
             .add(name='wqncode1', replicas=2)
             .add(name='encode2', replicas=2, needs='chunk_seg')
             .join(['wqncode1', 'encode2']))

        a.save_config('test2.yml')

        c = Flow.load_config('test2.yml')

        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.add_tmpfile('test2.yml')

    def test_dryrun(self):
        f = (Flow()
             .add(name='dummyEncoder', yaml_path='mwu-encoder/mwu_encoder.yml'))

        with f:
            f.dry_run()

    def test_pod_status(self):
        args = set_pod_parser().parse_args(['--replicas', '3'])
        with BasePod(args) as p:
            self.assertEqual(len(p.status), p.num_peas)
            for v in p.status:
                self.assertIsNotNone(v)

    def test_flow_no_container(self):
        f = (Flow()
             .add(name='dummyEncoder', yaml_path='mwu-encoder/mwu_encoder.yml'))

        with f:
            f.index(input_fn=random_docs(10), in_proto=True)

    def test_flow_yaml_dump(self):
        f = Flow(logserver_config='yaml/test-server-config.yml',
                 optimize_level=FlowOptimizeLevel.IGNORE_GATEWAY,
                 no_gateway=True)
        f.save_config('test1.yml')

        fl = Flow.load_config('test1.yml')
        self.assertEqual(f.args.logserver_config, fl.args.logserver_config)
        self.assertEqual(f.args.optimize_level, fl.args.optimize_level)
        self.add_tmpfile('test1.yml')

    def test_flow_log_server(self):
        f = Flow.load_config('yaml/test_log_server.yml')
        with f:
            self.assertTrue(hasattr(JINA_GLOBAL.logserver, 'ready'))
            a = requests.get(JINA_GLOBAL.logserver.ready, timeout=5)
            self.assertEqual(a.status_code, 200)

    def test_shards(self):
        f = Flow().add(name='doc_pb', yaml_path='yaml/test-docpb.yml', replicas=3, separated_workspace=True)
        with f:
            f.index(input_fn=random_docs(1000), in_proto=True, random_doc_id=False)
        with f:
            pass
        self.add_tmpfile('test-docshard')

    def test_shards_insufficient_data(self):
        index_docs = 3
        replicas = 4

        def validate(req):
            self.assertEqual(len(req.docs), 1)
            self.assertEqual(len(req.docs[0].topk_results), index_docs)

            for d in req.docs[0].topk_results:
                self.assertTrue(hasattr(d.match_doc, 'weight'))
                self.assertIsNotNone(d.match_doc.weight)
                self.assertEqual(d.match_doc.meta_info, b'hello world')

        f = Flow().add(name='doc_pb', yaml_path='yaml/test-docpb.yml', replicas=replicas, separated_workspace=True)
        with f:
            f.index(input_fn=random_docs(index_docs), in_proto=True, random_doc_id=False)
        with f:
            pass
        f = Flow().add(name='doc_pb', yaml_path='yaml/test-docpb.yml', replicas=replicas,
                       separated_workspace=True, polling='all', reducing_yaml_path='_merge_topk_docs')
        with f:
            f.search(input_fn=random_queries(1, index_docs), in_proto=True, random_doc_id=False, output_fn=validate,
                     callback_on_body=True)
        self.add_tmpfile('test-docshard')

    def test_py_client(self):
        f = (Flow().add(name='r1', yaml_path='_forward')
             .add(name='r2', yaml_path='_forward')
             .add(name='r3', yaml_path='_forward', needs='r1')
             .add(name='r4', yaml_path='_forward', needs='r2')
             .add(name='r5', yaml_path='_forward', needs='r3')
             .add(name='r6', yaml_path='_forward', needs='r4')
             .add(name='r8', yaml_path='_forward', needs='r6')
             .add(name='r9', yaml_path='_forward', needs='r5')
             .add(name='r10', yaml_path='_merge', needs=['r9', 'r8']))

        with f:
            f.dry_run()
            from jina.clients import py_client
            py_client(port_grpc=f.port_grpc, host=f.host).dry_run()


if __name__ == '__main__':
    unittest.main()
