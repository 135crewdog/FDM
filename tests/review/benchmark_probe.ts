// Paired steady-state Node timings. Each repetition starts from the same state.
// No per-step property logging; initialization and file loading excluded.
import {createSim} from '../../src/wasm.ts';
const sims=await Promise.all(['jsbsim','jsbsim-weh'].map(variant=>createSim({variant:variant as 'jsbsim'|'jsbsim-weh'})));
const results:Record<string,number[]>={};
for(let rep=0;rep<7;rep++) for(const model of ['c172x','f16']) {
  const order=rep%2===0?[0,1]:[1,0];
  for(const index of order) for(const integ of (rep%2===0?[1,5]:[5,1])) {
    const sim=sims[index];sim.reset();sim.setDebugLevel(0);sim.dt=1/1000;sim.loadModel(model);
    sim.setProperty('ic/h-sl-ft',10000);sim.setProperty('ic/u-fps',300);
    sim.setIntegrators({rateRotational:integ});sim.runIC();sim.runSteps(1000);
    const start=performance.now();
    const completed=sim.runSteps(5000);
    const elapsed=performance.now()-start;
    if(completed!==5000||!Number.isFinite(sim.getProperty('position/h-sl-ft'))) throw Error('invalid timing run');
    const key=`${index===0?'js':'wasm'} ${model} integrator=${integ}`;
    (results[key]??=[]).push(elapsed*1000/completed);
  }
}
for(const [key,samples] of Object.entries(results)) {
  const sorted=[...samples].sort((a,b)=>a-b);
  console.log(JSON.stringify({key,samples_us:samples,min_us:sorted[0],median_us:sorted[3],max_us:sorted[6]}));
}
for(const sim of sims)sim.delete();
