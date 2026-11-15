// Additional API diagnostics, separate from the frozen tests and shipped code.
import {createSim,describeError} from '../../src/wasm.ts';
const sim=await createSim();sim.setDebugLevel(0);
for(const dt of ['0','-0.01','nan']){
 sim.reset();sim.setDebugLevel(0);
 sim.writeFile('scripts/review-dt.xml',`<runscript name="bad dt"><use aircraft="c172x" initialize="reset00"/><run start="0" end="1" dt="${dt}"/></runscript>`);
 try{sim.loadScript('scripts/review-dt.xml');console.log(JSON.stringify({test:'script dt',requested:dt,accepted:true,actual_dt:sim.dt}));}
 catch(e){console.log(JSON.stringify({test:'script dt',requested:dt,accepted:false,error:describeError(e)}));}
}
sim.reset();sim.dt=1/480;sim.loadModel('c172x');sim.loadIC('reset00');sim.runIC();
sim.setIntegrators({rateRotational:1,rateTranslational:3});
try{sim.setIntegrators({rateRotational:5,rateTranslational:999});}
catch(e){console.log('ordinary invalid batch:',describeError(e),'remaining rate:',sim.getProperty('simulation/integrator/rate/rotational'));}
let reads=0;
const changing={rateRotational:5,get rateTranslational(){reads++;return reads<=3?3:999;}};
try{sim.setIntegrators(changing);}
catch(e){console.log('changing getter batch:',describeError(e),'reads:',reads,'remaining rate:',sim.getProperty('simulation/integrator/rate/rotational'));}
for(const p of ['simulation/integrator/rate/contact-active','simulation/integrator/rate/contact-switches',
 'simulation/integrator/midpoint/steps']){
 try{sim.setProperty(p,77);console.log('claimed read-only status write accepted:',p,'reads:',sim.getProperty(p));}
 catch(e){console.log('status write rejected:',p,describeError(e));}
}
for(const [p,v] of [['simulation/integrator/rate/contact-hold-sec',-1],
 ['simulation/integrator/rate/contact-release-mode',99]] as const){
 try{sim.setProperty(p,v);console.log('auxiliary setting write accepted:',p,'reads:',sim.getProperty(p));}
 catch(e){console.log('auxiliary write rejected:',p,describeError(e));}
}
sim.delete();
