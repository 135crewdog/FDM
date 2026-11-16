// Independent adversarial checks; run with npx tsx tests/review/review05_binding.ts.
import {createSim} from '../../src/wasm.ts';
const sim = await createSim({profile:'fdm'});
const props=['simulation/integrator/rate/rotational','simulation/integrator/position/rotational','gear/strut-limits/enabled'];
const state=()=>({dt:sim.dt,profile:sim.profile,settings:props.map(p=>sim.getProperty(p))});
sim.loadModel('c172x');sim.loadIC('reset00');sim.runIC();
console.log('loaded',state());
sim.setProperty('simulation/reset',1);console.log('simulation/reset',state());
sim.reset();sim.loadScript('scripts/c1723.xml');console.log('script implicit dt',state());
for (const [p,v] of [['simulation/integrator/rate/contact-release-mode',0.9],['gear/strut-limits/enabled',0.9]] as const) {
 let error='';try{sim.setProperty(p,v)}catch(e){error=String(e)}
 console.log('fractional setting',{p,v,read:sim.getProperty(p),error});
}
// A refused step is hidden in bulk outputs, but explicit refresh publishes it.
sim.reset();sim.loadModel('c172x');sim.loadIC('reset00');sim.runIC();
sim.bindOutputs(['simulation/sim-time-sec','position/h-agl-ft']);sim.readOutputs();
sim.setContainment({minCgHeightAglFt:1000});
const before=[...sim.outputs];const n=sim.step(1);console.log('refused',{n,before,outputs:[...sim.outputs],live:sim.getProperty('position/h-agl-ft'),halt:sim.halted});
sim.readOutputs();console.log('readOutputs after halt',[...sim.outputs]);
// Throw in a batch with containment off: accepted intermediate states are not published.
sim.reset();sim.setContainment(null);
sim.writeFile('scripts/review05_throw.xml','<runscript name="throw"><use aircraft="c172x" initialize="reset00"/><run start="0" end="10" dt="0.002"><event name="bad"><condition>simulation/sim-time-sec ge 0.1</condition><set name="simulation/integrator/rate/translational" value="7"/></event></run></runscript>');
sim.loadScript('scripts/review05_throw.xml');sim.runIC();sim.bindOutputs(['simulation/sim-time-sec']);sim.readOutputs();
try{sim.step(100)}catch(e){console.log('batch exception',{error:String(e),published:[...sim.outputs],live:sim.simTime,halt:sim.halted})}
sim.delete();
