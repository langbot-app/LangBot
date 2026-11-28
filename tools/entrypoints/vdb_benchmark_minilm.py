"""Private CPU MiniLM embedding endpoint used by the public RAG workload."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from tools.regression.vdb_benchmark_public import MODEL, assets_verified


class MiniLM:
    def __init__(self, assets, threads):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        assets_verified(assets, ('model.onnx', 'tokenizer.json'))
        self.tokenizer = Tokenizer.from_file(str(assets / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(assets / 'model.onnx'), options, providers=['CPUExecutionProvider'])

    def embed(self, texts):
        np = self.np
        encoded = self.tokenizer.encode_batch(texts)
        feed = {
            'input_ids': np.array([e.ids for e in encoded], dtype=np.int64),
            'attention_mask': np.array([e.attention_mask for e in encoded], dtype=np.int64),
            'token_type_ids': np.array([e.type_ids for e in encoded], dtype=np.int64),
        }
        features = self.session.run(['last_hidden_state'], feed)[0]
        mask = feed['attention_mask'][..., None].astype(np.float32)
        means = (features * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
        normalized = means / np.maximum(np.linalg.norm(means, axis=1, keepdims=True), 1e-12)
        return normalized.tolist(), int(mask.sum())


def handler(model):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status, data):
            response = json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *args):
            return

        def do_GET(self):
            self.send_json(200 if self.path == '/healthz' else 404, {})

        def do_POST(self):
            if self.path != '/v1/embeddings':
                self.send_json(404, {'error': 'route not found'})
                return
            try:
                size = int(self.headers.get('Content-Length', -1))
                if not 0 < size <= 4 * 1024 * 1024:
                    raise ValueError
                request = json.loads(self.rfile.read(size))
                texts = request['input']
                texts = [texts] if isinstance(texts, str) else texts
                if (
                    not isinstance(texts, list)
                    or not 1 <= len(texts) <= 256
                    or not all(isinstance(t, str) for t in texts)
                    or request.get('model') != MODEL
                ):
                    raise ValueError
            except (TypeError, ValueError, KeyError):
                self.send_json(400, {'error': 'invalid embedding request'})
                return
            try:
                embeddings, tokens = model.embed(texts)
                self.send_json(
                    200,
                    {
                        'object': 'list',
                        'model': MODEL,
                        'usage': {'prompt_tokens': tokens, 'total_tokens': tokens},
                        'data': [
                            {'object': 'embedding', 'index': i, 'embedding': vector}
                            for i, vector in enumerate(embeddings)
                        ],
                    },
                )
            except Exception as exc:
                print(type(exc).__name__, flush=True)
                self.send_json(500, {'error': 'local model failed'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--threads', type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    model = MiniLM(args.assets, args.threads)
    model.embed(['warm the ONNX model before opening the port'])
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler(model)) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
