const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(){
 const memory={};
 const ctx=vm.createContext({console,Date,JSON,Number,String,Error,
  PropertiesService:{getScriptProperties:()=>({getProperty:k=>memory[k]||null,setProperty:(k,v)=>memory[k]=v})},
  Utilities:{formatDate:(date,zone,format)=>{
   const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',hourCycle:'h23'}).formatToParts(date).map(p=>[p.type,p.value]));
   return format==='H'?parts.hour:`${parts.year}-${parts.month}-${parts.day}`;
  }}
 });
 vm.runInContext(fs.readFileSync(__dirname+'/Code.gs','utf8'),ctx);
 return {ctx,memory};
}
test('LA cutoff survives summer and winter clock changes',()=>{
 const {ctx}=setup();
 for(const [at,day] of [['2026-11-27T00:00:00Z','2026-11-26'],['2026-11-26T23:59:00Z','2026-11-25'],['2027-03-14T22:59:00Z','2027-03-13'],['2027-03-14T23:00:00Z','2027-03-14']]) assert.equal(ctx.dueDay(new Date(at)),day);
});
test('active run and cooldown prevent duplicate dispatches',()=>{
 const {ctx}=setup();let calls=[];
 ctx.github=(path,payload)=>{calls.push({path,payload});return payload?null:{workflow_runs:[{status:'in_progress'}]};};
 assert.equal(ctx.dispatch('daily.yml',{},new Date()),false);assert.equal(calls.length,1);
 calls=[];ctx.github=(path,payload)=>{calls.push({path,payload});return payload?null:{workflow_runs:[]};};
 assert.equal(ctx.dispatch('daily.yml',{report_date:'2026-11-26'},new Date()),true);
 assert.equal(ctx.dispatch('daily.yml',{},new Date()),false);
 assert.equal(calls.filter(c=>c.payload).length,1);
});
