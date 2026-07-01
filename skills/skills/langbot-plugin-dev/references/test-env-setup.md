# Test Environment Setup

## Docker Compose (GitOps)

Create in `server-deploy` repo under `servers/<hostname>/langbot-test/docker-compose.yaml`:

```yaml
version: "3"
services:
  langbot_plugin_runtime:
    image: rockchin/langbot:latest
    container_name: langbot-test-runtime
    volumes:
      - /opt/docker-data/langbot-test/data/plugins:/app/data/plugins
    ports:
      - "5411:5401"
    restart: on-failure
    environment:
      - TZ=Asia/Shanghai
    command: ["uv", "run", "--no-sync", "-m", "langbot_plugin.cli.__init__", "rt"]
    networks:
      - langbot_test_network

  langbot:
    image: rockchin/langbot:latest
    container_name: langbot-test
    volumes:
      - /opt/docker-data/langbot-test/data:/app/data
    ports:
      - "5310:5300"
    restart: on-failure
    depends_on:
      - langbot_plugin_runtime
    environment:
      - TZ=Asia/Shanghai
    networks:
      - langbot_test_network

networks:
  langbot_test_network:
    driver: bridge
```

## Post-Deploy Configuration

After first start, LangBot auto-generates `data/config.yaml`. You need to update `plugin.runtime_ws_url` to match the runtime container name:

```bash
# On the host, edit config
sed -i 's|ws://localhost:5400/control/ws|ws://langbot-test-runtime:5400/control/ws|' \
  /opt/docker-data/langbot-test/data/config.yaml
docker restart langbot-test
```

## Installing a Plugin

Copy plugin directory to `data/plugins/` on the host:

```bash
scp -r MyPlugin/ user@host:/opt/docker-data/langbot-test/data/plugins/MyPlugin/
docker restart langbot-test-runtime  # Runtime picks up new plugins on restart
```

## Caddy Reverse Proxy (Optional)

If testing externally, add to Caddyfile on the same host:

```
langbot-test.example.com {
    reverse_proxy langbot-test:5300
}
```

Then reload: `docker exec caddy caddy reload --config /etc/caddy/Caddyfile`

The WebSocket endpoint works through Caddy without special config.

## WebSocket Test Script (Node.js)

```javascript
const WebSocket = require('ws');

const PIPELINE_UUID = '<your-pipeline-uuid>';
const BASE = 'wss://langbot-test.example.com';
const URL = `${BASE}/api/v1/pipelines/${PIPELINE_UUID}/ws/connect?session_type=group`;

const ws = new WebSocket(URL, {
  headers: { Origin: BASE }
});

const send = (text) => {
  ws.send(JSON.stringify({
    type: 'message',
    message: [{ type: 'Plain', text }]
  }));
  console.log('[SENT]', text);
};

ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.type === 'connected') {
    console.log('Connected!');
    // Send test messages
    send('Message 1');
    setTimeout(() => send('Message 2'), 500);
    setTimeout(() => send('!summary'), 2000);
  } else if (msg.type === 'response' && msg.data?.is_final) {
    console.log('[BOT]', msg.data.content);
  }
});

ws.on('error', (e) => console.error('Error:', e.message));
setTimeout(() => { ws.close(); process.exit(); }, 60000);
```

Requires: `npm install ws`
