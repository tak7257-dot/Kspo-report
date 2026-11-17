// 본 건물에서 멀리 떨어진 부품(노드)을 지운다: 각 메시 노드의 월드 bbox 중심이 전체 중앙값에서 LIMIT(m) 넘게 떨어지면 삭제
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { getBounds, prune } from '@gltf-transform/functions';
const [,, input, output, limitArg] = process.argv;
const LIMIT = Number(limitArg || 80);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(input);
const nodes = doc.getRoot().listNodes().filter(n => n.getMesh());
const centers = nodes.map(n => { const b = getBounds(n); return b.min.map((v, i) => (v + b.max[i]) / 2); });
const med = [0, 1, 2].map(i => { const a = centers.map(c => c[i]).sort((x, y) => x - y); return a[Math.floor(a.length / 2)]; });
let removed = 0;
nodes.forEach((n, k) => {
  const b = getBounds(n);
  const far = Math.max(...[b.min, b.max].map(c => Math.hypot(...c.map((v, i) => v - med[i]))));   // 가장 먼 모서리
  if (far > LIMIT) { console.log('삭제:', n.getName() || n.getMesh().getName(), 'min', b.min.map(v => v.toFixed(0)), 'max', b.max.map(v => v.toFixed(0))); n.dispose(); removed++; }
});
await doc.transform(prune());
await io.write(output, doc);
console.log(`노드 ${nodes.length}개 중 ${removed}개 삭제 (중심 ${med.map(v => v.toFixed(1))}, 기준 ${LIMIT}m)`);
