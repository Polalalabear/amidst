import test from 'node:test';
import assert from 'node:assert/strict';
import {PerspectiveCamera,Vector3} from 'three';
import {worldDirectionProjection,worldDirectionSVG} from './geometry.mjs';

const close=(actual,expected,tolerance=1e-9)=>assert.ok(Math.abs(actual-expected)<tolerance,`${actual} != ${expected}`);
const byLabel=rows=>Object.fromEntries(rows.map(row=>[row.label,row]));

test('Z-up cardinal views keep world directions right handed and screen Y downward',()=>{
  const alongX=byLabel(worldDirectionProjection(0,0));
  close(alongX['+Y'].x,1);close(alongX['+Y'].y,0);
  close(alongX['−Y'].x,-1);close(alongX['+Z'].y,-1);
  close(alongX['+X'].x,0);close(alongX['+X'].y,0);close(alongX['+X'].depth,1);
  const alongY=byLabel(worldDirectionProjection(Math.PI/2,0));
  close(alongY['+X'].x,-1);close(alongY['−X'].x,1);close(alongY['+Z'].y,-1);
  const angled=byLabel(worldDirectionProjection(.61,.77));
  for(const axis of ['X','Y'])for(const component of ['x','y','depth'])close(angled['+'+axis][component],-angled['−'+axis][component]);
  assert.ok(angled['+Z'].y<0,'positive world Z points toward the top of the screen');
});

test('direction projection matches actual Three Z-up cameras without mirroring at translated targets',()=>{
  const views=[{yaw:-1.2,pitch:.08,target:[35,44,.37],distance:3},
    {yaw:.7,pitch:.77,target:[-8,3,7],distance:17},
    {yaw:2.6,pitch:1.3,target:[13,-22,4],distance:8},
    {yaw:-2.2,pitch:-.3,target:[-19,-6,-2],distance:11}];
  for(const {yaw,pitch,target:xyz,distance} of views){
    const target=new Vector3(...xyz),original=target.clone(),camera=new PerspectiveCamera(43,1,.01,10000);
    camera.up.set(0,0,1);
    camera.position.set(target.x+distance*Math.cos(pitch)*Math.cos(yaw),target.y+distance*Math.cos(pitch)*Math.sin(yaw),target.z+distance*Math.sin(pitch));
    camera.lookAt(target);camera.updateMatrixWorld();
    const center=target.clone().project(camera);
    for(const direction of worldDirectionProjection(yaw,pitch)){
      const endpoint=target.clone();endpoint[direction.axis.toLowerCase()]+=.1*direction.sign;
      const projected=endpoint.project(camera),screen=[projected.x-center.x,-(projected.y-center.y)];
      const renderedLength=Math.hypot(...screen),helperLength=Math.hypot(direction.x,direction.y);
      assert.ok(renderedLength>1e-8&&helperLength>1e-8);
      close(screen[0]/renderedLength,direction.x/helperLength);
      close(screen[1]/renderedLength,direction.y/helperLength);
    }
    assert.deepEqual(target,original,'projection must not translate or rotate source targets');
  }
});

test('compass SVG contains only world-axis direction labels and remains finite at edge-on views',()=>{
  for(const [yaw,pitch] of [[0,0],[Math.PI/2,0],[-1.2,.77],[.4,1.48]]){
    const svg=worldDirectionSVG(yaw,pitch);
    assert.equal((svg.match(/data-world-axis=/g)??[]).length,5);
    for(const label of ['+X','−X','+Y','−Y','+Z'])assert.ok(svg.includes(`data-world-axis="${label}"`));
    assert.ok(svg.includes('來源世界軸'));assert.ok(svg.includes('Z-up'));
    assert.doesNotMatch(svg,/NaN|Infinity|門|走廊|東|北|米|metres/i);
  }
  assert.notEqual(worldDirectionSVG(.3,.77),worldDirectionSVG(.5,.77));
  for(const [yaw,pitch] of [[NaN,.4],[Infinity,.4],[.4,NaN],[.4,Infinity],[0,Math.PI/2],[0,-Math.PI/2]]){
    assert.equal(worldDirectionProjection(yaw,pitch),null);assert.equal(worldDirectionSVG(yaw,pitch),'');
  }
});
