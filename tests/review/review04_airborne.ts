// Numerical stress diagnostic, NOT a model of a real aircraft or a new gate.
// Spherical inertia J=I, initial p=0.1 rad/s, no contacts. Damping Mx=-c*p
// has the independent exact answer p(t)=0.1*exp(-c*t) when evaluated in-core.
// The bulk-hook version also exposes any execution-order delay in feedback.
import {createSim} from '../../src/wasm.ts';
const sim=await createSim({dirs:[]});
const xml=(c:number,hook:boolean)=>`<fdm_config version="2.0" release="BETA">
 <planet><rotation_rate>0</rotation_rate></planet>
 <metrics/><mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy>
 <izz unit="SLUG*FT2">1</izz><emptywt unit="LBS">32.174049</emptywt></mass_balance>
 <ground_reactions/>
 ${hook?'<external_reactions><moment name="damp" frame="BODY"><direction><x>1</x><y>0</y><z>0</z></direction></moment></external_reactions>':''}
 <aerodynamics>${hook?'':`<axis name="ROLL"><function name="linear-damper"><product><value>${-c}</value><property>velocities/pi-rad_sec</property></product></function></axis>`}</aerodynamics>
</fdm_config>`;
for(const c of [100,200,400])for(const hook of [false,true])for(const hz of [480,960,1000])for(const rate of [1,5,10]){
 sim.reset();sim.setDebugLevel(0);sim.dt=1/hz;
 sim.writeFile('aircraft/probe/probe.xml',xml(c,hook));sim.loadModel('probe');
 sim.setProperty('ic/h-sl-ft',100000);sim.setProperty('ic/p-rad_sec',0.1);
 sim.setIntegrators({rateRotational:rate,positionRotational:7,rateRotationalOnContact:1});
 if(hook)sim.setProperty('external_reactions/damp/magnitude-lbsft',-c*0.1);
 sim.runIC();const hp=sim.handle('velocities/pi-rad_sec');
 if(hook){sim.bindInputs(['external_reactions/damp/magnitude-lbsft']);sim.bindOutputs([hp]);}
 let runaway:number|null=null,exception:string|null=null,peak=0,err=0;
 const first:number[]=[sim.get(hp)];
 for(let k=0;k<hz;k++){
  try{
   if(hook){sim.inputs[0]=-c*sim.get(hp);sim.step(1);}else sim.run();
  }catch(e){exception=String(e);break;}
  const p=sim.get(hp);if(first.length<9)first.push(p);
  if(!Number.isFinite(p)||Math.abs(p)>1e6){runaway=sim.simTime;break;}
  peak=Math.max(peak,Math.abs(p));err=Math.max(err,Math.abs(p-0.1*Math.exp(-c*sim.simTime)));
 }
 console.log(JSON.stringify({c_per_s:c,hook,hz,rate_integrator:rate,contact_points:sim.getProperty('gear/num-units'),
  runaway,exception,peak_rate:peak,max_error_vs_continuous_solution:err,end_p:sim.get(hp),first_rates:first}));
}
sim.delete();
