import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {createSim} from '../../src/wasm.ts';
const c=JSON.parse(readFileSync(new URL('./parity_config.json',import.meta.url),'utf8'));
mkdirSync('out/review',{recursive:true});
const sim=await createSim();
for (const model of c.models) for (const integ of c.integrators) {
  sim.reset();sim.setDebugLevel(0);sim.dt=1/c.hz;sim.loadModel(model);
  for (const [p,v] of Object.entries(c.initial)) sim.setProperty(p,v as number);
  sim.setIntegrators({rateRotational:integ});sim.runIC();
  for (const p of c.properties) if(!sim.hasProperty(p)) throw Error(p);
  const rows=[c.properties.join(',')];
  const sample=()=>rows.push(c.properties.map((p:string)=>sim.getProperty(p).toPrecision(17)).join(','));
  sample();
  for(let k=0;k<c.hz*c.seconds;k++) {
    for(const [p,n] of [['fcs/elevator-cmd-norm',128],['fcs/aileron-cmd-norm',256],['fcs/rudder-cmd-norm',512]] as const)
      sim.setProperty(p,(Math.floor(k/n)%3-1)/128);
    if(!sim.run()) throw Error('early stop'); sample();
  }
  writeFileSync(`out/review/${model}-${integ}-wasm.csv`,rows.join('\n')+'\n');
  console.log(model,integ,'wasm complete');
}
sim.delete();
