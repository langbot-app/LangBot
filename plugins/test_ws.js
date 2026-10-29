const WebSocket = require('ws');

const PIPELINE = '48963ec3-5f45-4078-a81e-ce0c569566fd';
const URL = `wss://langbot-test.rockchin.top/api/v1/pipelines/${PIPELINE}/ws/connect?session_type=group`;

console.log(`Connecting to ${URL}`);
const ws = new WebSocket(URL, { headers: { Origin: 'https://langbot-test.rockchin.top' } });

ws.on('open', () => console.log('Connected!'));
ws.on('error', e => console.error('Error:', e.message));
ws.on('close', (c, r) => console.log(`Closed: ${c} ${r}`));

ws.on('message', data => {
  const msg = JSON.parse(data.toString());
  console.log('[RECV]', JSON.stringify(msg, null, 2).substring(0, 800));
});

// Helper: build a Plain text message chain
function textMsg(text) {
  return {
    type: 'message',
    message: [{ type: 'Plain', text }],
  };
}

const msgs = [
  '大家好，今天的会议几点开始？',
  '下午3点，讨论新版本的发布计划',
  '好的，我准备了性能测试报告',
  'Bob那边CI/CD流程改好了吗',
  '改好了，现在自动部署到staging了',
  '我觉得我们应该先修复那个内存泄漏的问题',
  '同意，内存泄漏在高并发下会导致OOM',
  '那就优先级调高，这个版本必须修',
  '我来负责修这个，预计需要两天',
  '我可以帮忙review代码',
];

async function run() {
  // Wait for connected
  await new Promise(r => {
    const handler = (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.type === 'connected') { ws.removeListener('message', handler); r(); }
    };
    ws.on('message', handler);
  });

  console.log('\n--- Sending 10 group messages ---');
  for (const text of msgs) {
    ws.send(JSON.stringify(textMsg(text)));
    console.log(`[SENT] ${text}`);
    await new Promise(r => setTimeout(r, 1000));
  }

  console.log('\n--- Waiting 3s then sending !summary ---');
  await new Promise(r => setTimeout(r, 3000));
  ws.send(JSON.stringify(textMsg('!summary')));
  console.log('[SENT] !summary');

  // Wait for bot response
  console.log('--- Waiting 30s for response ---');
  await new Promise(r => setTimeout(r, 30000));

  console.log('\n--- Sending NL summary request ---');
  ws.send(JSON.stringify(textMsg('请帮我总结一下群聊内容')));
  console.log('[SENT] 请帮我总结一下群聊内容');

  console.log('--- Waiting 30s for response ---');
  await new Promise(r => setTimeout(r, 30000));

  console.log('\nDone.');
  ws.close();
}

ws.on('open', run);
