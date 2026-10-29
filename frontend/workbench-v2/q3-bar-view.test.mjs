import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {mount} from './q3-bar-view.mjs';
import {parsedExecutionRequest} from './app.mjs';

class Element {
  constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.listeners={};this.value='';}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  setAttribute(key,value){this.attributes[key]=value;}
  addEventListener(key,listener){this.listeners[key]=listener;}
  removeEventListener(key){delete this.listeners[key];}
}
function find(root,predicate){if(predicate(root))return root;for(const child of root.children){const result=find(child,predicate);if(result)return result;}return null;}
async function setup(available=true){
  const wrapper=JSON.parse(await readFile(new URL('fixtures/q-bootstrap.json',import.meta.url),'utf8'));
  const run=JSON.parse(wrapper.bootstrap_json).runs[0];run.q3_llm_available=available;
  let state={activeRun:run,loading:false,q3:null,reviewMode:false,task:'q2',switchMode:'AGENT_SEQUENTIAL'};
  let render;const store={getState:()=>state,subscribe:fn=>{render=fn;return()=>{};}};
  const requests=[],root=new Element('div');
  globalThis.document={createElement:tag=>new Element(tag)};
  const view=mount({store,slots:{query:root},api:{getSession:()=> 'SYNTHETIC_SESSION'},execute:q=>requests.push(q)});
  return {root,requests,view,setState:update=>{state={...state,...update};render(state);}};
}

test('Q3 mode is explicit and independent from the Q5 mode; default remains RULE',async()=>{
  const s=await setup();const select=find(s.root,x=>x.attributes['aria-label']==='Q3 解析模式');
  const text=find(s.root,x=>x.attributes['aria-label']==='文字查詢');text.value='車13:00:00到13:00:01';
  const form=find(s.root,x=>x.tag==='form');form.listeners.submit({preventDefault(){}});
  assert.equal(s.requests[0].parser_mode,'RULE_ONLY');
  select.value='LLM_WITH_RULE_FALLBACK';form.listeners.submit({preventDefault(){}});
  assert.equal(s.requests[1].parser_mode,'LLM_WITH_RULE_FALLBACK');
  assert.equal(Object.hasOwn(s.requests[1],'switch_mode'),false);s.view.destroy();delete globalThis.document;
});
test('unconfigured Q3 model cannot be selected or submitted by editing a disabled option',async()=>{
  const s=await setup(false);const select=find(s.root,x=>x.attributes['aria-label']==='Q3 解析模式');
  assert.equal(select.children[1].disabled,true);select.value='LLM_WITH_RULE_FALLBACK';
  find(s.root,x=>x.tag==='form').listeners.submit({preventDefault(){}});
  assert.equal(s.requests.length,0);assert.match(find(s.root,x=>x.className==='q3-status').textContent,/Q3_LLM_NOT_CONFIGURED/);
  s.view.destroy();delete globalThis.document;
});
test('changing source resets Q3 selection and loading disables its control',async()=>{
  const s=await setup();const select=find(s.root,x=>x.attributes['aria-label']==='Q3 解析模式');select.value='LLM_WITH_RULE_FALLBACK';
  s.setState({activeRun:{...JSON.parse(JSON.parse(await readFile(new URL('fixtures/q-bootstrap.json',import.meta.url),'utf8')).bootstrap_json).runs[0],q3_llm_available:false}});
  assert.equal(select.value,'RULE_ONLY');s.setState({loading:true});assert.equal(select.disabled,true);
  s.view.destroy();delete globalThis.document;
});
test('parsed Q2 uses operator Q5 policy without mutating the parse response or Q1 request',()=>{
  const response={status:'PARSED',output_sha256:'a'.repeat(64),structured_query:{schema_version:'q-demo.q2-request.v1',switch_mode:'RULE_ONLY'}};
  const original=structuredClone(response),next=parsedExecutionRequest(response,'AGENT_SEQUENTIAL');
  assert.equal(next.switch_mode,'AGENT_SEQUENTIAL');assert.deepEqual(response,original);
  const q1={status:'PARSED',structured_query:{schema_version:'q-demo.q1-request.v1',origin:'Q3_PARSED'}};
  assert.deepEqual(parsedExecutionRequest(q1,'AGENT_SEQUENTIAL'),q1.structured_query);
  assert.throws(()=>parsedExecutionRequest({status:'NEEDS_CLARIFICATION'},'RULE_ONLY'));
  assert.throws(()=>parsedExecutionRequest(response,'UNKNOWN'));
});
