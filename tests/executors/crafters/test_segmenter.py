from jina.executors.crafters import BaseSegmenter
from jina.flow import Flow
from jina.proto import jina_pb2
from tests import JinaTestCase


def random_docs(num_docs):
    for j in range(num_docs):
        yield jina_pb2.Document()


class DummySegment(BaseSegmenter):
    def craft(self):
        return [dict(raw_bytes=b'aa'), dict(raw_bytes=b'bb')]


class MyTestCase(JinaTestCase):
    def get_chunk_id(self, req):
        id = 0
        for d in req.index.docs:
            for c in d.chunks:
                self.assertEqual(c.chunk_id, id)
                id += 1

    def collect_chunk_id(self, req):
        chunk_ids = [c.chunk_id for d in req.index.docs for c in d.chunks]
        self.assertTrue(len(chunk_ids), len(set(chunk_ids)))

    def test_dummy_seg(self):
        f = Flow().add(yaml_path='DummySegment')
        with f:
            f.index(input_fn=random_docs(10), in_proto=True, output_fn=self.get_chunk_id)

    def test_dummy_seg_random(self):
        f = Flow().add(yaml_path='../../yaml/dummy-seg-random.yml')
        with f:
            f.index(input_fn=random_docs(10), in_proto=True, output_fn=self.collect_chunk_id)
