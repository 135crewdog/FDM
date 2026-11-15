// WASM replication of three native matrix cases. No model/config changes.
import {createSim} from '../../src/wasm.ts';
const sim=await createSim();
for(const [model,scenario,seconds] of [['c172x','rest',60],['737','hard',15],['ah1s','inverted',15]] as const)
 for(const hz of [480,1000]) for(const integrator of [1,5]) {
  sim.reset();sim.setDebugLevel(0);
  const init=model==='c172x'?'reset_at_rest':'reset00';
  sim.writeFile('scripts/review-spot.xml',`<runscript name="review"><use aircraft="${model}" initialize="${init}"/><run start="0" end="100" dt="${1/hz}"/></runscript>`);
  sim.loadScript('scripts/review-spot.xml',1/hz);
  if(scenario!=='rest') for(const [p,v] of Object.entries({'ic/h-agl-ft':40,'ic/phi-deg':scenario==='inverted'?180:0,
    'ic/theta-deg':0,'ic/vn-fps':100,'ic/ve-fps':0,'ic/vd-fps':scenario==='inverted'?80:30}))sim.setProperty(p,v);
  sim.setIntegrators({rateRotational:integrator});sim.runIC();
  const props=['velocities/p-rad_sec','velocities/q-rad_sec','velocities/r-rad_sec','position/h-agl-ft',
    'velocities/v-north-fps','velocities/v-east-fps','velocities/v-down-fps'];
  const hs=props.map(p=>sim.handle(p));
  const initial=hs.map(h=>sim.get(h));
  let bad:number|null=null,tailPeak=0;
  for(let k=0;k<seconds*hz;k++) {
    if(!sim.run())throw Error('early end');
    const v=hs.map(h=>sim.get(h));
    if(!v.every(Number.isFinite)){bad=sim.simTime;break;}
    if(sim.simTime>=seconds-10)tailPeak=Math.max(tailPeak,...v.slice(0,3).map(Math.abs));
  }
  console.log(JSON.stringify({model,scenario,hz,integrator,first_nonfinite:bad,tail_peak_rate:tailPeak,
    initial,end_time:sim.simTime,end:hs.map(h=>sim.get(h))}));
 }
sim.delete();
