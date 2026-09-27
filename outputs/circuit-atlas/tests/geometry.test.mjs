import test from 'node:test';
import assert from 'node:assert/strict';
import {changeOrientation,nodeMatrix,transformPoint,nodeBounds} from '../dist/geometry.js';

test('rotation preserves center and four turns restore all pin coordinates',()=>{
 const original={x:120,y:100};let layout=original;
 const before=transformPoint(nodeMatrix(original,184,130),0,79);
 layout=changeOrientation(layout,'rotate');
 assert.deepEqual(transformPoint(nodeMatrix(layout,184,130),92,65),{x:212,y:165});
 assert.deepEqual(transformPoint(nodeMatrix(layout,184,130),0,79),{x:198,y:73});
 for(let n=0;n<3;n++)layout=changeOrientation(layout,'rotate');
 assert.deepEqual(transformPoint(nodeMatrix(layout,184,130),0,79),before);
});

test('screen-horizontal reflection works at every rotation and is reversible',()=>{
 for(const rotation of [0,90,180,270])for(const mirrored of [false,true]){
   const a={x:-80,y:34,rotation,mirrored};const b=changeOrientation(a,'mirror');
   const p=transformPoint(nodeMatrix(a,184,130),14,79),q=transformPoint(nodeMatrix(b,184,130),14,79);
   assert.equal(q.x,2*(a.x+92)-p.x);assert.equal(q.y,p.y);
   assert.deepEqual(changeOrientation(b,'mirror'),a);
 }
});

test('bounds include corners after rotation, including negative coordinates',()=>{
 const layout={x:0,y:0,rotation:90};
 assert.deepEqual(nodeBounds(layout,184,130),{minX:27,minY:-27,maxX:157,maxY:157});
});
