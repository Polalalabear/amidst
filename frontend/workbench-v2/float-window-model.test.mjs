import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_STATE,STORAGE_KEY,clampPos,loadState,saveState,toggled,moved,isToggleKey} from './float-window-model.mjs';
const mem=(init={})=>{const m=new Map(Object.entries(init));return {getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,v),m};};
test('default state is closed with no stored position (never covers a camera tile)',()=>{
  assert.deepEqual(loadState(mem()),{open:false,pos:null});assert.equal(DEFAULT_STATE.open,false);
});
test('state round-trips through storage',()=>{
  const st=mem();assert.equal(saveState({open:true,pos:{x:10,y:20}},st),true);
  assert.deepEqual(loadState(st),{open:true,pos:{x:10,y:20}});
});
test('storage failures and garbage fall back to the default',()=>{
  const throwing={getItem(){throw new Error('SecurityError');},setItem(){throw new Error('QuotaExceeded');}};
  assert.deepEqual(loadState(throwing),{open:false,pos:null});assert.equal(saveState({open:true,pos:null},throwing),false);
  assert.deepEqual(loadState(null),{open:false,pos:null});
  assert.deepEqual(loadState(mem({[STORAGE_KEY]:'{not json'})),{open:false,pos:null});
  assert.deepEqual(loadState(mem({[STORAGE_KEY]:JSON.stringify({open:'yes',pos:{x:'a',y:1}})})),{open:false,pos:null});
});
test('toggle and drag keep the window inside its container',()=>{
  assert.equal(toggled({open:false,pos:null}).open,true);
  const b={width:800,height:500},s={width:300,height:200};
  assert.deepEqual(clampPos({x:-5,y:900},s,b),{x:0,y:300});
  assert.deepEqual(moved({open:true,pos:null},{x:1000,y:10},s,b),{open:true,pos:{x:500,y:10}});
});
test('M toggles unless typing or a modifier is held',()=>{
  assert.equal(isToggleKey({key:'m',target:{tagName:'DIV'}}),true);assert.equal(isToggleKey({key:'M',target:{tagName:'BUTTON'}}),true);
  assert.equal(isToggleKey({key:'m',target:{tagName:'INPUT'}}),false);assert.equal(isToggleKey({key:'m',ctrlKey:true,target:{}}),false);
  assert.equal(isToggleKey({key:'x',target:{}}),false);
});
